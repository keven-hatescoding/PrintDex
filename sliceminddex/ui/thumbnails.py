"""Carrega as miniaturas da Biblioteca em segundo plano.

Pedir uma miniatura ao Windows leva de dezenas a centenas de ms por arquivo
(mais na primeira vez, quando o gerador abre o modelo). Isso roda em threads
próprias e o resultado volta à interface pela fila do app; a tela nunca
espera. As imagens prontas ficam num cache em memória: voltar a uma pasta ou
atualizar a tela (ex.: a IA moveu um arquivo) não pede tudo de novo.

Threads daemon, e não um ThreadPoolExecutor: um gerador de miniaturas
travado (de outro programa) nunca impede o app de fechar.
"""

import queue
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image

from sliceminddex.core.thumbnail_helper import get_thumbnail

WORKERS = 3
CACHE_SIZE = 300  # miniaturas em memória (50 a 110 KB cada, conforme a escala de DPI)

MISSING = object()  # lookup(): ainda não carregada

# Chave: (caminho, (mtime_ns, tamanho), pixels). Mudou o arquivo, muda a chave.
Key = tuple


@dataclass
class _Job:
    key: Key
    path: str
    size: int
    generation: int
    callbacks: list[Callable] = field(default_factory=list)


class ThumbnailLoader:
    def __init__(self, deliver: Callable[..., None]) -> None:
        """`deliver(func, *args)` executa func na thread da interface."""
        self._deliver = deliver
        self._queue: queue.Queue[_Job] = queue.Queue()
        self._lock = threading.Lock()  # protege tudo abaixo
        self._cache: OrderedDict[Key, Image.Image | None] = OrderedDict()
        self._jobs: dict[Key, _Job] = {}  # na fila ou sendo carregadas
        self._generation = 0
        self._threads: list[threading.Thread] = []

    def lookup(self, key: Key) -> Image.Image | None | object:
        """Imagem do cache, None (o arquivo não tem miniatura) ou MISSING."""
        with self._lock:
            if key not in self._cache:
                return MISSING
            self._cache.move_to_end(key)
            return self._cache[key]

    def request(self, key: Key, path: str, size: int,
                callback: Callable[[Image.Image | None], None]) -> None:
        """Carrega em segundo plano; callback(imagem ou None) roda na thread
        da interface. Chame da thread da interface."""
        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                job = _Job(key, path, size, self._generation)
                self._jobs[key] = job
                self._queue.put(job)
            elif job.generation != self._generation:
                # Pedida antes de uma troca de pasta: os cards antigos já não existem
                job.generation = self._generation
                job.callbacks.clear()
            job.callbacks.append(callback)
        self._start_workers()

    def new_generation(self) -> None:
        """Descarta os pedidos ainda na fila (o usuário mudou de pasta)."""
        with self._lock:
            self._generation += 1

    def _start_workers(self) -> None:
        if self._threads:
            return
        for index in range(WORKERS):
            thread = threading.Thread(target=self._work, daemon=True,
                                      name=f"SliceMindDex-Thumbnails-{index + 1}")
            thread.start()
            self._threads.append(thread)

    def _work(self) -> None:
        while True:
            job = self._queue.get()
            with self._lock:
                if job.generation != self._generation:
                    del self._jobs[job.key]  # de uma pasta que já foi fechada
                    continue
            try:
                image = get_thumbnail(job.path, job.size)
            except Exception:  # um arquivo problemático não pode derrubar a thread
                image = None
            with self._lock:
                del self._jobs[job.key]
                self._cache[job.key] = image
                self._cache.move_to_end(job.key)
                while len(self._cache) > CACHE_SIZE:
                    self._cache.popitem(last=False)
                callbacks = job.callbacks if job.generation == self._generation else []
            for callback in callbacks:
                self._deliver(callback, image)
