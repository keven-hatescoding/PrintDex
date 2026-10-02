"""Serviço de monitoramento: Watchdog + fila de organização, sem interface.

A interface só chama start()/stop()/shutdown() e recebe eventos por
callbacks. Eles podem ser chamados de qualquer thread (Watchdog, verificadora,
pool da IA), então quem os recebe precisa repassá-los à thread da interface:

    on_log(Msg)            linha para o painel de atividade
    on_state(state)        "stopped" | "running" | "stopping"
    on_stats(Stats)        contadores atualizados
    on_organized(result)   um arquivo foi movido (ex.: atualizar a Biblioteca)
"""

import os
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from printdex.config import GEMINI_MAX_RPM
from printdex.core.organizer import Cancelled, OrganizeResult, organize_file
from printdex.core.watcher import FolderMonitor
from printdex.locales import Msg

# Chamadas simultâneas ao Gemini (o total por minuto é limitado por
# GEMINI_MAX_RPM, em config.py)
ORGANIZER_WORKERS = 2


@dataclass(frozen=True)
class Stats:
    """Contadores desde que o app foi aberto."""

    organized: int = 0  # classificados e movidos
    unknown: int = 0    # a IA falhou: movidos para Desconhecidos
    errors: int = 0     # não puderam ser movidos
    queued: int = 0     # na fila ou em processamento agora


@dataclass
class _Session:
    """Um ciclo start -> stop. Cada sessão tem o próprio pool, para que stop()
    descarte a fila sem afetar a próxima sessão."""

    monitor: FolderMonitor
    executor: ThreadPoolExecutor
    cancel: threading.Event  # libera quem espera o limite da API


class MonitorService:
    def __init__(
        self,
        on_log: Callable[[Msg], None],
        on_state: Callable[[str], None],
        on_stats: Callable[[Stats], None] | None = None,
        on_organized: Callable[[OrganizeResult], None] | None = None,
    ) -> None:
        self._on_log = on_log
        self._on_state = on_state
        self._on_stats = on_stats
        self._on_organized = on_organized
        self.state = "stopped"

        self._session: _Session | None = None
        # Arquivos na fila ou em processamento (caminho -> Future). Fica fora da
        # sessão: se o monitoramento for parado e iniciado de novo antes de a
        # fila esvaziar, a nova varredura não reenvia o que está em andamento.
        self._jobs: dict[str, Future] = {}
        self._lock = threading.Lock()  # protege _jobs e _counts
        self._counts = {"organized": 0, "unknown": 0, "errors": 0}

    # ------------------------------------------------------------- controle

    def start(self, source: str, dest_root: str, api_key: str) -> None:
        """Liga o Watchdog e, em seguida, a varredura inicial (outra thread).

        Lança a exceção do Watchdog se a pasta não puder ser monitorada.
        """
        if self._session is not None:
            return
        executor = ThreadPoolExecutor(
            max_workers=ORGANIZER_WORKERS, thread_name_prefix="PrintDex-Organizer"
        )
        cancel = threading.Event()
        # Destino e chave ficam fixos nesta sessão (capturados pelo lambda)
        monitor = FolderMonitor(
            source,
            on_file_ready=lambda path: self._submit(executor, cancel, path,
                                                    dest_root, api_key),
            on_error=self._on_log,
            on_scan_complete=self._on_scan_complete,
            # O Watchdog ignora eventos de arquivos que já estão na fila
            is_busy=self.is_queued,
        )
        try:
            monitor.start()
        except Exception:
            executor.shutdown(wait=False)
            raise
        self._session = _Session(monitor, executor, cancel)
        self._set_state("running")

    def stop(self) -> None:
        """Para em segundo plano: o join() do Observer pode levar ~1 s."""
        session, self._session = self._session, None
        if session is None:
            return
        self._set_state("stopping")

        def worker() -> None:
            left = self._end_session(session)
            self._on_log(Msg("log.monitor_stopped"))
            if left:
                self._on_log(Msg("log.queue_left", count=left))
            self._set_state("stopped")

        threading.Thread(target=worker, name="PrintDex-Stop", daemon=True).start()

    def shutdown(self, timeout: float = 2.0) -> None:
        """Encerra na hora (ao fechar o app). Tarefas em andamento terminam."""
        session, self._session = self._session, None
        if session is not None:
            self._end_session(session, timeout)

    def stats(self) -> Stats:
        with self._lock:
            return Stats(queued=len(self._jobs), **self._counts)

    def is_queued(self, path: str) -> bool:
        """True se o arquivo está na fila ou sendo organizado agora.

        Consultado pelo Watchdog (outra thread) para ignorar a rajada de
        eventos de um arquivo que já vai ser processado.
        """
        with self._lock:
            return path in self._jobs

    # -------------------------------------------------------------- interno

    def _set_state(self, state: str) -> None:
        self.state = state
        self._on_state(state)

    def _end_session(self, session: _Session, timeout: float = 5.0) -> int:
        """Para o monitor e descarta a fila da sessão.

        Retorna quantos arquivos saíram da fila sem serem processados. Eles
        continuam na pasta de origem; tarefas que já estão falando com a API
        ou movendo o arquivo terminam normalmente.
        """
        session.monitor.stop(timeout)  # depois disto nada novo entra na fila
        session.cancel.set()           # libera quem espera o limite da API
        with self._lock:
            futures = list(self._jobs.values())
        cancelled = sum(1 for future in futures if future.cancel())
        session.executor.shutdown(wait=False)
        return cancelled

    def _on_scan_complete(self, count: int) -> None:
        """Chamado pela thread verificadora ao fim da varredura inicial."""
        if count == 0:
            self._on_log(Msg("log.scan_none"))
            return
        self._on_log(Msg("log.scan_found", count=count))
        if count > GEMINI_MAX_RPM:
            self._on_log(Msg("log.rate_hint", n=GEMINI_MAX_RPM))

    def _submit(self, executor: ThreadPoolExecutor, cancel: threading.Event,
                path: str, dest_root: str, api_key: str) -> None:
        """Chamado pela thread verificadora quando um arquivo está pronto
        (download concluído ou encontrado na varredura inicial).

        Só enfileira e retorna na hora: a chamada ao Gemini roda no pool, sem
        atrasar a detecção dos próximos arquivos.
        """
        name = os.path.basename(path)
        with self._lock:
            if path in self._jobs:
                return  # já está na fila ou sendo processado
            # Loga antes de enfileirar para "detectado" vir antes de "Analisando"
            self._on_log(Msg("log.file_detected", name=name))
            try:
                future = executor.submit(self._organize_job, name, path,
                                         dest_root, api_key, cancel)
            except RuntimeError:
                return  # pool já encerrado: o monitoramento está parando
            self._jobs[path] = future
        self._emit_stats()
        # Fora do lock: se o Future já terminou, o callback roda aqui mesmo
        future.add_done_callback(lambda _future: self._forget(path))

    def _forget(self, path: str) -> None:
        with self._lock:
            self._jobs.pop(path, None)
        self._emit_stats()

    def _count(self, kind: str) -> None:
        with self._lock:
            self._counts[kind] += 1
        self._emit_stats()

    def _emit_stats(self) -> None:
        if self._on_stats:
            self._on_stats(self.stats())

    def _organize_job(self, name: str, path: str, dest_root: str,
                      api_key: str, cancel: threading.Event) -> None:
        """Roda numa thread do pool."""
        if cancel.is_set():
            self._on_log(Msg("log.cancelled", name=name))
            return
        self._on_log(Msg("log.analyzing", name=name))
        try:
            result = organize_file(name, path, dest_root, api_key, cancel)
        except Cancelled:
            self._on_log(Msg("log.cancelled", name=name))
            return
        except FileNotFoundError:
            self._on_log(Msg("log.file_vanished", name=name))
            self._count("errors")
            return
        except OSError as exc:
            self._on_log(Msg("log.move_error", name=name, error=str(exc)))
            self._count("errors")
            return
        except Exception as exc:  # nunca deixar a falha passar em silêncio
            self._on_log(Msg("log.unexpected_error", name=name, error=str(exc)))
            self._count("errors")
            return

        if result.duplicate:
            # Já existia um arquivo idêntico no destino: a cópia da origem foi apagada
            existing = os.path.relpath(result.destination, dest_root).replace(os.sep, " / ")
            self._on_log(Msg("log.duplicate_discarded", name=name, existing=existing))
            return

        # O nome vai no fim porque até 2 arquivos são analisados em paralelo
        files = name if result.final_name == name else f"{name} -> {result.final_name}"
        if result.classified:
            folders = f"{result.categoria_principal} / {result.franquia} / {result.tipo_item}"
            self._on_log(Msg("log.success", path=folders, files=files))
            self._count("organized")
        else:
            # A pasta de falha depende do idioma (Unknown / Desconhecidos)
            unknown_folder = os.path.basename(os.path.dirname(result.destination))
            self._on_log(Msg("log.ai_error", folder=unknown_folder, files=files,
                             reason=result.ai_error))
            self._count("unknown")
        if self._on_organized:
            self._on_organized(result)
