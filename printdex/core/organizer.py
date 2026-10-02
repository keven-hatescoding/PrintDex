"""Classificação via Google Gemini e movimentação dos arquivos.

Estrutura gerada (3 níveis, baseada em franquias):
    PRINTS / categoria_principal / franquia / tipo_item / nome_limpo.ext
    ex.: PRINTS / Animes e Mangas / Dragon Ball / Busto / Vegeta.stl

A categoria é sempre uma das CATEGORIES (lista fechada no prompt, no schema
e conferida no código); franquia e tipo de item são livres.

`organize_file()` é síncrona e bloqueia por 1-3 s (rede), ou mais quando o
limite de chamadas por minuto (GEMINI_MAX_RPM) foi atingido. Ela deve ser
chamada de uma thread de trabalho (o app usa um ThreadPoolExecutor), nunca da
thread da interface nem da thread do Watchdog.
"""

import contextlib
import errno
import filecmp
import json
import os
import re
import shutil
import threading
import time
import unicodedata
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, NamedTuple

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

from printdex.config import (
    GEMINI_ATTEMPTS,
    GEMINI_MAX_RPM,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_MS,
    SUPPORTED_EXTENSIONS,
    UNKNOWN_FOLDER,
)
from printdex.locales import Msg

# Únicas categorias permitidas (1º nível de pastas). A IA não pode criar
# outras: sem isso ela espalhava a mesma coisa em "Cultura Pop",
# "Personagens", "Miniaturas/Anime"...
CATEGORIES = (
    "Animes e Mangas",
    "Filmes e Series",
    "Jogos",
    "Utilitarios e Ferramentas",
    "Decoracao",
    "Automotivo",
    "Cosplay e Acessorios",
    "Outros",
)
OTHER_CATEGORY = "Outros"  # destino se a IA, mesmo assim, fugir da lista

PROMPT_TEMPLATE = (
    "És um classificador avançado de ficheiros para impressão 3D. Analisa o "
    "nome deste ficheiro e identifica a que universo/franquia ele pertence. "
    "Deves retornar ÚNICA e EXCLUSIVAMENTE um objeto JSON válido contendo: "
    "'categoria_principal', 'franquia' (usa 'Geral' se não pertencer a "
    "nenhuma), 'tipo_item' (a utilidade ou formato da peça) e 'nome_limpo'. "
    "Ignora extensões e números de versão.\n\n"
    "CLASSIFICAÇÃO OBRIGATÓRIA: A 'categoria_principal' deve ser EXATAMENTE "
    "UMA destas opções: " + ", ".join(f"'{name}'" for name in CATEGORIES) + ". "
    "Nunca crie uma categoria nova. Se for um personagem de anime (ex: Vegeta, "
    "Zoro, Midoriya), coloque SEMPRE em 'Animes e Mangas'. Na chave "
    "'franquia', coloque o universo (ex: 'Dragon Ball', 'One Piece'). Na chave "
    "'tipo_item', coloque o formato (ex: 'Miniatura', 'Busto', 'Suporte').\n\n"
    "Ficheiro: {nome_do_arquivo}"
)

NO_FRANCHISE = "Geral"
# Variações que a IA às vezes usa no lugar de "Geral" (comparadas via _fold)
_NO_FRANCHISE_ALIASES = {
    "geral", "nenhuma", "nenhum", "sem franquia", "none", "null", "n/a", "na",
    "-", "generico", "generica", "desconhecida", "desconhecido",
}

MOVE_ATTEMPTS = 5          # arquivo em uso: tenta de novo algumas vezes
MOVE_RETRY_DELAY = 1.0     # segundos (cresce a cada tentativa)
MAX_FOLDER_NAME = 60
MAX_FILE_STEM = 100

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Escolher pastas/nome livre + mover precisa ser atômico: com 2 workers, dois
# arquivos que a IA chamou de "Benchy" poderiam pegar o mesmo "Benchy.stl"
# e um sobrescreveria o outro.
_move_lock = threading.Lock()


class Classificacao(BaseModel):
    """Schema enviado ao Gemini. As descrições também orientam o modelo.

    `categoria_principal` é um Literal: o SDK o envia como enum, e a API só
    consegue gerar um dos valores da lista.
    """

    categoria_principal: Literal[*CATEGORIES] = Field(description=(
        "Exatamente uma das categorias permitidas. Personagens de anime "
        "(ex.: Vegeta, Zoro, Midoriya) vão sempre em 'Animes e Mangas'"
    ))
    franquia: str = Field(description=(
        "Universo, franquia ou marca a que o modelo pertence. Ex.: Dragon "
        "Ball, One Piece, Harry Potter, Porsche. Obrigatoriamente 'Geral' se "
        "não pertencer a nenhuma"
    ))
    tipo_item: str = Field(description=(
        "Formato ou utilidade da peça. Ex.: Miniatura, Busto, Suporte"
    ))
    nome_limpo: str = Field(description=(
        "Nome bem formatado para o ficheiro, sem extensão nem número de versão"
    ))


class ClassificationError(Exception):
    """Falha da IA: rede, cota, chave inválida, JSON inválido etc.

    `msg` é o motivo traduzível, exibido no log no idioma da interface.
    """

    def __init__(self, msg: Msg) -> None:
        super().__init__(msg.key)
        self.msg = msg

    def __str__(self) -> str:
        return self.msg.render()


class Cancelled(Exception):
    """O monitoramento parou antes da chamada à API; o arquivo não foi tocado."""


class RateLimiter:
    """Permite no máximo `max_calls` chamadas por `period` segundos.

    Compartilhado por todas as threads do pool (o limite da API é por
    projeto, não por thread). A espera pode ser interrompida por um Event.
    """

    def __init__(self, max_calls: int, period: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self, cancel: threading.Event | None = None) -> None:
        """Bloqueia até liberar uma vaga. Lança Cancelled se `cancel` for setado."""
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                delay = self.period - (now - self._calls[0])
            if cancel is None:
                time.sleep(delay)
            elif cancel.wait(delay):
                raise Cancelled()


_rate_limiter = RateLimiter(GEMINI_MAX_RPM)


@dataclass(frozen=True)
class Classification:
    categoria_principal: str
    franquia: str
    tipo_item: str
    nome_limpo: str  # já sanitizado; pode ser "" se a IA não devolver nada útil

    @property
    def folders(self) -> tuple[str, str, str]:
        return (self.categoria_principal, self.franquia, self.tipo_item)


@dataclass(frozen=True)
class OrganizeResult:
    destination: str                    # caminho final do arquivo
    # Pastas realmente usadas: podem diferir da resposta da IA em maiúsculas
    # ou acentos quando uma pasta equivalente já existia
    categoria_principal: str | None = None
    franquia: str | None = None
    tipo_item: str | None = None
    ai_error: Msg | None = None         # motivo, quando caiu no fallback
    # True: já existia um arquivo idêntico; `destination` é ele e o arquivo
    # da origem foi apagado
    duplicate: bool = False

    @property
    def classified(self) -> bool:
        return self.ai_error is None

    @property
    def final_name(self) -> str:
        return os.path.basename(self.destination)


# ------------------------------------------------------------------ IA

@lru_cache(maxsize=4)
def _get_client(api_key: str) -> genai.Client:
    """Reaproveita o cliente (e sua conexão HTTP) entre chamadas."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=GEMINI_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=GEMINI_ATTEMPTS),
        ),
    )


def _fold(text: str) -> str:
    """Chave de comparação sem acentos nem maiúsculas: "Pokémon" == "pokemon"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def sanitize_name(name: object, max_length: int = MAX_FOLDER_NAME) -> str:
    """Transforma o texto da IA num nome de pasta/arquivo seguro no Windows.

    Remove separadores e caracteres proibidos (impede path traversal como
    "../.."), nomes reservados e pontos/espaços finais.
    """
    if not isinstance(name, str):
        return ""
    name = _INVALID_CHARS.sub(" ", name)
    name = " ".join(name.split())[:max_length]
    name = name.strip(" .")
    if name.upper() in _WINDOWS_RESERVED:
        name += "_"
    return name


def _clean_franchise(franquia: object) -> str:
    """Franquia sanitizada; qualquer forma de "nenhuma" vira "Geral"."""
    if not isinstance(franquia, str) or _fold(franquia.strip()) in _NO_FRANCHISE_ALIASES:
        return NO_FRANCHISE
    return sanitize_name(franquia) or NO_FRANCHISE


def _canonical_category(value: object) -> str | None:
    """A categoria da lista fixa, com a grafia exata dela.

    Aceita diferença de maiúsculas e acentos ("animes e mangás"). Uma
    categoria fora da lista vira "Outros" (nunca uma pasta nova); vazia
    retorna None (resposta incompleta da IA).
    """
    if not isinstance(value, str) or not value.strip():
        return None
    key = _fold(value.strip())
    for category in CATEGORIES:
        if _fold(category) == key:
            return category
    return OTHER_CATEGORY


def _clean_file_stem(nome_limpo: object) -> str:
    """Sanitiza o nome_limpo para usar como nome de arquivo (sem extensão)."""
    if isinstance(nome_limpo, str):
        # A IA às vezes devolve "Naruto.stl" mesmo instruída a ignorar extensões.
        # Só remove extensões 3D conhecidas: "Mr. Bean" não pode virar "Mr".
        stem, ext = os.path.splitext(nome_limpo.strip())
        if ext.lower() in SUPPORTED_EXTENSIONS:
            nome_limpo = stem
    return sanitize_name(nome_limpo, MAX_FILE_STEM)


def classify(file_name: str, api_key: str,
             cancel: threading.Event | None = None) -> Classification:
    """Pergunta ao Gemini como classificar e renomear o arquivo.

    Respeita GEMINI_MAX_RPM; lança Cancelled se `cancel` for setado enquanto
    espera a vez.
    """
    _rate_limiter.wait(cancel)
    try:
        response = _get_client(api_key).models.generate_content(
            model=GEMINI_MODEL,
            contents=PROMPT_TEMPLATE.format(nome_do_arquivo=file_name),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",  # sem markdown em volta
                response_schema=Classificacao,
                # temperature fica no padrão (1.0): o Google recomenda não
                # reduzi-la nos modelos Gemini 3, sob risco de piorar a qualidade
                # Sem ferramentas: desliga o AFC (e o aviso que o SDK emite)
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except errors.APIError as exc:
        raise ClassificationError(
            Msg("ai.api_error", code=exc.code, message=exc.message)
        ) from exc
    except httpx.HTTPError as exc:
        raise ClassificationError(Msg("ai.connection", error=str(exc))) from exc
    except Exception as exc:
        raise ClassificationError(Msg("ai.unexpected", error=str(exc))) from exc

    text = response.text
    if not text:
        raise ClassificationError(Msg("ai.empty"))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClassificationError(Msg("ai.invalid_json", text=repr(text[:120]))) from exc
    if not isinstance(data, dict):
        raise ClassificationError(Msg("ai.unexpected_json", text=repr(text[:120])))

    # O enum do schema já obriga a API a usar a lista; isto é a rede de segurança
    categoria = _canonical_category(data.get("categoria_principal"))
    tipo_item = sanitize_name(data.get("tipo_item"))
    if not categoria or not tipo_item:
        raise ClassificationError(Msg("ai.missing_fields", text=repr(text[:120])))

    # franquia vazia vira "Geral"; nome_limpo vazio mantém o nome original
    return Classification(
        categoria_principal=categoria,
        franquia=_clean_franchise(data.get("franquia")),
        tipo_item=tipo_item,
        nome_limpo=_clean_file_stem(data.get("nome_limpo")),
    )


# ---------------------------------------------------------- arquivos

def _folder_key(name: str) -> str:
    """Chave para reconhecer a mesma pasta escrita de outro jeito: sem
    acentos, sem maiúsculas e sem o "s" do plural ("Miniatura" == "miniaturas")."""
    key = _fold(name)
    return key[:-1] if len(key) > 3 and key.endswith("s") else key


def _existing_variant(parent: str, name: str) -> str:
    """Retorna o nome de uma subpasta já existente equivalente a `name`, ou o
    próprio `name`.

    Evita fragmentar a árvore quando a IA varia a grafia entre chamadas:
    "Dragon ball" vai para a pasta "Dragon Ball" já existente, e "Miniatura"
    para "Miniaturas".
    """
    key = _folder_key(name)
    match = None
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                if entry.is_dir() and _folder_key(entry.name) == key:
                    if entry.name == name:
                        return name
                    match = match or entry.name
    except FileNotFoundError:
        pass
    return match or name


def _resolve_dir(root: str, folders: Sequence[str]) -> str:
    """Monta root/pasta1/pasta2/... O 1º nível (categoria, ou Desconhecidos)
    usa sempre o nome exato; só franquia e tipo reaproveitam variações."""
    path = root
    for depth, name in enumerate(folders):
        path = os.path.join(path, _existing_variant(path, name) if depth else name)
    return path


def _same_content(src: str, other: str, size: int) -> bool:
    """True se `other` é um arquivo idêntico a `src` (tamanho e bytes)."""
    try:
        return (os.path.isfile(other) and os.path.getsize(other) == size
                and filecmp.cmp(src, other, shallow=False))
    except OSError:
        return False


def _place(folder: str, file_name: str, src: str) -> tuple[str, bool]:
    """Escolhe o destino do arquivo dentro de `folder`.

    Retorna (caminho, duplicata). Antes de usar o próximo nome livre
    ("Naruto (1).stl", "Naruto (2).stl"...), compara o conteúdo: se já existe
    na pasta um arquivo idêntico, retorna esse arquivo com duplicata=True.
    Também confere os outros arquivos da pasta com o mesmo tamanho, porque a
    IA pode ter dado outro nome à mesma peça.
    """
    size = os.path.getsize(src)
    stem, ext = os.path.splitext(file_name)
    candidate, counter = os.path.join(folder, file_name), 1
    while os.path.exists(candidate):
        if _same_content(src, candidate, size):
            return candidate, True
        candidate = os.path.join(folder, f"{stem} ({counter}){ext}")
        counter += 1
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.is_file() and _same_content(src, entry.path, size):
                return entry.path, True
    return candidate, False


def _move_once(src: str, dst: str) -> None:
    """Move src -> dst sem nunca deixar cópia extra para trás.

    Na mesma unidade, os.rename é atômico (e falha se o arquivo estiver
    aberto em outro programa; aí a próxima tentativa recomeça do zero). Entre
    unidades, copia e apaga a origem; se apagar falhar, desfaz a cópia.

    O shutil.move copiava quando o rename falhava por "arquivo em uso" e
    deixava a cópia no destino a cada nova tentativa: era a origem dos
    "arquivo (1)", "arquivo (2)" idênticos.
    """
    try:
        os.rename(src, dst)
        return
    except OSError as exc:
        # Outra unidade: errno EXDEV (no Windows, WinError 17)
        if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
            raise
    try:
        shutil.copy2(src, dst)
        os.remove(src)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(dst)
        raise


class MoveResult(NamedTuple):
    path: str        # onde o arquivo ficou (ou a cópia idêntica que já existia)
    duplicate: bool  # True: era clone; o arquivo da origem foi apagado


def move_file(src: str, dest_root: str, folders: Sequence[str] = (),
              new_name: str | None = None) -> MoveResult:
    """Move o arquivo para `dest_root / folders...`, criando as pastas e
    opcionalmente renomeando.

    Se a pasta já tem um arquivo idêntico, o da origem é descartado (apagado)
    em vez de virar "nome (1)". Se o arquivo estiver em uso (PermissionError
    no Windows), tenta de novo algumas vezes antes de desistir. Outros
    OSError são propagados.
    """
    file_name = new_name or os.path.basename(src)
    for attempt in range(1, MOVE_ATTEMPTS + 1):
        with _move_lock:
            dest_dir = _resolve_dir(dest_root, folders)
            # Sem permissão na pasta de destino não adianta repetir: falha já
            os.makedirs(dest_dir, exist_ok=True)
            target, duplicate = _place(dest_dir, file_name, src)
            try:
                if duplicate:
                    os.remove(src)  # clone: fica só o que já estava no destino
                else:
                    _move_once(src, target)
                return MoveResult(target, duplicate)
            except PermissionError:
                if attempt == MOVE_ATTEMPTS:
                    raise
        time.sleep(MOVE_RETRY_DELAY * attempt)  # fora do lock
    raise AssertionError("inalcançável")


def organize_file(
    file_name: str, file_path: str, dest_root: str, api_key: str,
    cancel: threading.Event | None = None,
) -> OrganizeResult:
    """Classifica o arquivo com a IA e o move para
    `dest_root / categoria_principal / franquia / tipo_item / nome_limpo.ext`.

    Se a IA falhar, move para `dest_root / Desconhecidos` com o nome original.
    Erros ao mover (arquivo sumiu, em uso, sem permissão) são propagados como
    OSError e o arquivo continua na pasta de origem. Se `cancel` for setado
    antes da chamada à API, lança Cancelled sem tocar no arquivo.
    """
    try:
        result = classify(file_name, api_key, cancel)
    except ClassificationError as exc:
        moved = move_file(file_path, dest_root, (UNKNOWN_FOLDER,))
        return OrganizeResult(destination=moved.path, ai_error=exc.msg,
                              duplicate=moved.duplicate)

    # Mantém a extensão original (inclusive maiúsculas: ".OBJ" continua ".OBJ")
    new_name = None
    if result.nome_limpo:
        new_name = result.nome_limpo + os.path.splitext(file_name)[1]

    moved = move_file(file_path, dest_root, result.folders, new_name)
    categoria, franquia, tipo_item = Path(moved.path).parent.parts[-3:]
    return OrganizeResult(
        destination=moved.path,
        categoria_principal=categoria,
        franquia=franquia,
        tipo_item=tipo_item,
        duplicate=moved.duplicate,
    )
