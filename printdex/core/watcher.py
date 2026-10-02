"""Monitoramento da pasta de origem com Watchdog.

Como os navegadores salvam downloads:
- Chrome/Edge/Opera: gravam em "arquivo.stl.crdownload" e, ao terminar,
  renomeiam para "arquivo.stl" (evento on_moved).
- Firefox: cria "arquivo.stl" vazio (placeholder), grava em
  "arquivo.stl.part" e, ao terminar, renomeia o .part por cima do placeholder.
- Cópia manual (Explorer): on_created seguido de vários on_modified enquanto
  o arquivo cresce.

Por isso o handler não reporta o arquivo no instante do evento: ele apenas
o coloca numa fila de "pendentes". Uma thread verificadora só libera o
arquivo quando ele tem tamanho > 0, o tamanho ficou estável por alguns
segundos, não existe arquivo temporário irmão (.part/.crdownload) e o
arquivo não está travado por outro processo.

Varredura inicial (catch-up): ao iniciar, os arquivos 3D que já estão na raiz
da pasta (baixados com o app fechado) entram na mesma fila de pendentes. Assim
eles passam pelas mesmas verificações — um download do Firefox em andamento
nesse momento não é enviado pela metade — e um arquivo visto tanto pela
varredura quanto pelo Watchdog é processado uma vez só.
"""

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from printdex.config import SUPPORTED_EXTENSIONS
from printdex.locales import Msg

# Sufixos que navegadores usam enquanto o download está em andamento
TEMP_SUFFIXES = (".crdownload", ".part", ".partial", ".download",
                 ".opdownload", ".tmp")


def is_model_file(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def find_model_files(folder: str) -> list[str]:
    """Arquivos 3D na raiz de `folder` (subpastas não são verificadas).

    Os caminhos são montados como os do Watchdog (pasta + nome), para que o
    mesmo arquivo tenha a mesma chave na fila de pendentes.
    """
    with os.scandir(folder) as entries:
        return [entry.path for entry in entries
                if is_model_file(entry.name) and entry.is_file()]


def _has_temp_sibling(path: str) -> bool:
    """Ex.: existe "modelo.stl.part" ao lado de "modelo.stl" (Firefox)."""
    return any(os.path.exists(path + suffix) for suffix in TEMP_SUFFIXES)


def _is_locked(path: str) -> bool:
    """No Windows, abrir para escrita falha se outro processo ainda está
    gravando o arquivo. O modo "ab" não altera o conteúdo."""
    try:
        with open(path, "ab"):
            return False
    except OSError:
        return True


class ModelFileHandler(FileSystemEventHandler):
    """Recebe eventos do Watchdog e mantém a fila de arquivos 3D pendentes.

    Proteção contra eventos repetidos (um download gera vários on_created e
    on_modified seguidos):
    - `_pending` é indexado pelo caminho: a rajada vira uma entrada só;
    - `_reported` guarda (tamanho, mtime): o mesmo arquivo sem mudança não é
      reportado de novo;
    - `is_busy(caminho)`: arquivo que já está na fila ou sendo organizado é
      ignorado até terminar.
    """

    def __init__(self, settle_seconds: float = 2.0,
                 is_busy: Callable[[str], bool] | None = None) -> None:
        super().__init__()
        self.settle_seconds = settle_seconds
        self._is_busy = is_busy
        self._lock = threading.Lock()
        # caminho -> (último tamanho visto, momento da última mudança)
        self._pending: dict[str, tuple[int, float]] = {}
        # caminho -> (tamanho, mtime) já reportado, para não repetir o aviso
        self._reported: dict[str, tuple[int, int]] = {}

    # Eventos do Watchdog (executam na thread do Observer)

    def on_created(self, event: FileSystemEvent) -> None:
        self.track(event.src_path, event.is_directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        self.track(event.src_path, event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        # Ex.: "modelo.stl.crdownload" -> "modelo.stl"
        self.track(event.dest_path, event.is_directory)

    def track(self, path: str | bytes, is_directory: bool = False) -> None:
        """Coloca o arquivo na fila de pendentes (eventos e varredura inicial)."""
        path = os.fsdecode(path)
        if is_directory or not is_model_file(path):
            return
        if self._is_busy is not None and self._is_busy(path):
            return  # já na fila ou sendo organizado: ignora até terminar
        with self._lock:
            # Qualquer novo evento reinicia a contagem de estabilidade
            self._pending[path] = (-1, time.monotonic())

    # Verificação (executa na thread verificadora do FolderMonitor)

    def pop_ready(self) -> list[str]:
        """Retorna os arquivos pendentes cujo download já terminou."""
        ready: list[str] = []
        now = time.monotonic()

        with self._lock:
            for path, (last_size, last_change) in list(self._pending.items()):
                try:
                    stat = os.stat(path)
                except FileNotFoundError:
                    del self._pending[path]  # foi apagado ou renomeado
                    continue
                except OSError:
                    continue  # sem acesso no momento; tenta de novo depois

                if stat.st_size != last_size:
                    self._pending[path] = (stat.st_size, now)
                    continue
                if stat.st_size == 0 or now - last_change < self.settle_seconds:
                    continue
                if _has_temp_sibling(path) or _is_locked(path):
                    continue

                del self._pending[path]
                signature = (stat.st_size, stat.st_mtime_ns)
                if self._reported.get(path) == signature:
                    continue  # mesmo arquivo, evento repetido
                self._reported[path] = signature
                ready.append(path)

        return ready


class FolderMonitor:
    """Gerencia o Observer do Watchdog e a thread que libera arquivos prontos.

    O Observer roda na própria thread dele; a varredura inicial e a verificação
    de estabilidade rodam em outra thread. Nenhuma das duas toca na interface:
    elas só chamam os callbacks, que devem ser thread-safe.
    """

    def __init__(
        self,
        folder: str,
        on_file_ready: Callable[[str], None],
        on_error: Callable[[Msg], None] | None = None,
        on_scan_complete: Callable[[int], None] | None = None,
        is_busy: Callable[[str], bool] | None = None,
        poll_interval: float = 0.5,
        settle_seconds: float = 2.0,
    ) -> None:
        self.folder = folder
        self.on_file_ready = on_file_ready
        self.on_error = on_error
        self.on_scan_complete = on_scan_complete
        # Consulta "este caminho já está na fila?" (ver ModelFileHandler)
        self.is_busy = is_busy
        self.poll_interval = poll_interval
        self.settle_seconds = settle_seconds

        self._observer: Observer | None = None
        self._checker: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def start(self) -> None:
        """Inicia o monitoramento. Lança OSError se a pasta for inválida."""
        if self.is_running:
            return

        handler = ModelFileHandler(self.settle_seconds, self.is_busy)
        observer = Observer()
        # Não recursivo: só a raiz da pasta de origem é monitorada
        observer.schedule(handler, self.folder, recursive=False)
        observer.start()

        self._stop_event.clear()
        self._observer = observer
        self._checker = threading.Thread(
            target=self._check_loop, args=(handler,),
            name="PrintDex-Checker", daemon=True,
        )
        self._checker.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Para o Observer e aguarda as threads terminarem."""
        self._stop_event.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout)
            self._observer = None
        if self._checker is not None:
            self._checker.join(timeout)
            self._checker = None

    def _initial_scan(self, handler: ModelFileHandler) -> None:
        """Enfileira os arquivos baixados enquanto o app estava fechado.

        Roda depois de o Observer já estar ativo: o que chegar durante a
        varredura também é capturado, e a fila (indexada por caminho) evita
        duplicatas.
        """
        try:
            paths = find_model_files(self.folder)
        except OSError as exc:
            if self.on_error:
                self.on_error(Msg("log.scan_error", error=str(exc)))
            return
        for path in paths:
            handler.track(path)
        if self.on_scan_complete:
            self.on_scan_complete(len(paths))

    def _check_loop(self, handler: ModelFileHandler) -> None:
        self._initial_scan(handler)
        while not self._stop_event.wait(self.poll_interval):
            for path in handler.pop_ready():
                try:
                    self.on_file_ready(path)
                except Exception as exc:  # não deixa a thread morrer
                    if self.on_error:
                        self.on_error(Msg("log.process_error", path=path, error=str(exc)))
