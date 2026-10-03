"""Uma instância só do SliceMind DEX por usuário.

Com o app escondido na bandeja, abrir o atalho de novo criaria um segundo
SliceMind DEX monitorando a mesma pasta (cada arquivo iria duas vezes para a IA)
e um segundo ícone na bandeja. Em vez disso, o segundo processo acorda o
primeiro, que mostra a janela, e sai.

No Windows, um evento nomeado faz as duas coisas: se ele já existe, há outra
instância (e SetEvent a acorda); se não, uma thread desta instância espera
nele. Este módulo não importa nada pesado: o segundo processo sai na hora.
"""

import sys
import threading
from collections.abc import Callable
from functools import lru_cache

_EVENT_NAME = "Local\\SliceMindDex.SingleInstance"  # "Local": por sessão de usuário
_ERROR_ALREADY_EXISTS = 183
_INFINITE = 0xFFFFFFFF
_WAIT_OBJECT_0 = 0


@lru_cache(maxsize=1)
def _kernel32():
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL,
                                      wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


class Instance:
    """A instância em execução (a primeira a abrir)."""

    def __init__(self, handle) -> None:
        self._handle = handle

    def on_activate(self, callback: Callable[[], None]) -> None:
        """Chama `callback` (numa thread própria) sempre que alguém tentar
        abrir o SliceMind DEX de novo."""
        if self._handle is None:
            return

        def wait() -> None:
            while _kernel32().WaitForSingleObject(self._handle, _INFINITE) == _WAIT_OBJECT_0:
                callback()

        threading.Thread(target=wait, name="SliceMindDex-Instance", daemon=True).start()


def acquire() -> Instance | None:
    """Instance se esta é a primeira; None se já havia outra (que foi acordada
    para mostrar a janela). Fora do Windows não há proteção."""
    if sys.platform != "win32":
        return Instance(None)
    import ctypes

    kernel32 = _kernel32()
    handle = kernel32.CreateEventW(None, False, False, _EVENT_NAME)  # reset automático
    if not handle:
        return Instance(None)  # sem o evento, segue sem a proteção
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.SetEvent(handle)
        kernel32.CloseHandle(handle)
        return None
    return Instance(handle)
