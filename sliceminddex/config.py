"""Constantes globais e caminhos padrão do aplicativo."""

import os
import sys
from pathlib import Path

from platformdirs import user_data_dir, user_documents_dir

APP_NAME = "SliceMind DEX"
# Nome anterior do app (até a 1.2.1-BETA). Usado só para trazer os dados de
# quem atualiza: o banco antigo e o destino padrão das primeiras versões.
LEGACY_APP_NAME = "PrintDex"

# Interface. Idiomas disponíveis em sliceminddex/locales.py (en, pt_BR, zh_CN).
DEFAULT_LANGUAGE = "en"
THEMES = ("System", "Dark", "Light")  # "System" segue o modo claro/escuro do Windows
DEFAULT_THEME = "System"

# Mesmo AppId do setup.iss: o app lê dali o idioma escolhido no instalador
INSTALLER_APP_ID = "{8C88A66D-4411-41A6-93BF-463A05AA3E69}"

# Dados internos do app (banco), no diretório padrão do SO:
#   Windows: %APPDATA%\SliceMind DEX   macOS: ~/Library/Application Support/SliceMind DEX
#   Linux:   ~/.local/share/SliceMind DEX
APP_DATA_DIR = Path(user_data_dir(APP_NAME, appauthor=False, roaming=True))
DB_PATH = APP_DATA_DIR / "sliceminddex.db"

# Bancos de versões anteriores, do mais recente ao mais antigo. Na primeira
# execução o primeiro que existir é copiado para DB_PATH (o antigo fica como
# backup): quem atualiza mantém pastas, API Key, idioma e calculadora.
LEGACY_DB_PATHS = (
    # %APPDATA%\PrintDex\printdex.db (até a 1.2.1-BETA)
    Path(user_data_dir(LEGACY_APP_NAME, appauthor=False, roaming=True)) / "printdex.db",
    # Pasta "data/" do projeto (primeiras versões de desenvolvimento)
    Path(__file__).resolve().parent.parent / "data" / "printdex.db",
)

# Arquivos que acompanham o app: na raiz do projeto ou, no .exe do
# PyInstaller, na pasta temporária onde ele se extrai (sys._MEIPASS)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
APP_ICON = RESOURCE_DIR / "app_icon.ico"

# Toda a árvore gerada pela IA fica dentro de uma pasta PRINTS.
PRINTS_FOLDER = "PRINTS"

# Padrão no Windows: C:\Program Files (x86)\SliceMind DEX\PRINTS, como a Steam.
# Quem cria a pasta é o instalador (setup.iss), já com permissão de escrita
# para o grupo Usuários: o app, os fatiadores e o Explorer gravam ali sem
# administrador. O banco continua no AppData. A variável de ambiente cobre um
# Windows instalado em outra unidade.
if sys.platform == "win32":
    _PROGRAM_FILES_X86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    DEFAULT_DEST_DIR = Path(_PROGRAM_FILES_X86) / APP_NAME / PRINTS_FOLDER
else:
    DEFAULT_DEST_DIR = Path(user_documents_dir()) / APP_NAME / PRINTS_FOLDER

# Padrão das primeiras versões (Documentos/PrintDex/PRINTS). Quem ainda usa
# exatamente este destino é levado ao novo padrão; escolhas manuais ficam.
# Quem usava o padrão da 1.x (Program Files (x86)\PrintDex\PRINTS) continua
# nele: a biblioteca não muda de lugar sozinha.
PREVIOUS_DEFAULT_DEST_DIR = Path(user_documents_dir()) / LEGACY_APP_NAME / PRINTS_FOLDER


def with_prints_folder(path: str) -> str:
    """Garante que o caminho termine em PRINTS.

    "D:/Impressoes" -> "D:/Impressoes/PRINTS"; "D:/Impressoes/PRINTS" fica
    igual (não duplica se o usuário selecionar a própria pasta PRINTS).
    """
    path = os.path.normpath(path)
    if os.path.basename(path).casefold() == PRINTS_FOLDER.casefold():
        return path
    return os.path.join(path, PRINTS_FOLDER)

# Extensões de arquivos 3D monitoradas
SUPPORTED_EXTENSIONS = {".stl", ".3mf", ".obj"}

# Gemini. O gemini-1.5-flash já foi desativado pelo Google; o Flash-Lite é a
# opção mais rápida e barata da geração atual. Se o reconhecimento de
# franquias ficar fraco, "gemini-3.8-flash" tem mais conhecimento (é um pouco
# mais lento e caro). Modelos vigentes:
# https://ai.google.dev/gemini-api/docs/deprecations
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT_MS = 20_000
GEMINI_ATTEMPTS = 3  # novas tentativas automáticas em 429/5xx
# Máximo de chamadas por minuto feitas pelo app. A varredura inicial pode
# enfileirar dezenas de arquivos de uma vez; sem este freio, o nível gratuito
# devolve erro 429 e os arquivos cairiam em "Desconhecidos". Veja o seu limite
# real em AI Studio > Rate limits e ajuste (no nível pago pode ser bem maior).
GEMINI_MAX_RPM = 10

# Os nomes das pastas criadas pela IA (categorias, "Unknown"/"Desconhecidos",
# "General"/"Geral") seguem o idioma: veja FOLDER_NAMES em core/organizer.py
