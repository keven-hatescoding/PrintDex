"""Miniaturas de arquivos 3D, as mesmas que o Explorer do Windows mostra.

    get_thumbnail(caminho, 256) -> PIL.Image (RGBA) ou None

Fontes, nesta ordem:
1. Windows (IShellItemImageFactory, chamado com ctypes, sem pywin32): usa o
   gerador de miniaturas registrado para o tipo do arquivo e o cache de
   miniaturas do Explorer. O Windows 11 traz o da Microsoft para .3mf;
   fatiadores e o Visualizador 3D podem registrar outros (.stl, .obj).
2. Miniatura embutida no .3mf: os fatiadores (Bambu Studio, PrusaSlicer,
   OrcaSlicer, Cura...) gravam uma imagem dentro do arquivo.
3. None: quem chama mostra um ícone genérico.

Pode ser chamado de qualquer thread (cada uma inicializa o COM na primeira
chamada), mas leva de dezenas a centenas de ms por arquivo: nunca na thread
da interface.
"""

import ctypes
import io
import os
import posixpath
import sys
import threading
import uuid
import zipfile
from xml.etree import ElementTree

from PIL import Image

# Imagens embutidas maiores que isto são ignoradas (arquivo malformado)
_MAX_EMBEDDED_BYTES = 16 * 1024 * 1024
# Relação do padrão OPC que aponta a miniatura do pacote (_rels/.rels)
_THUMBNAIL_RELATIONSHIP = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"
# Sem a relação: nomes usados pelos fatiadores, do mais ao menos comum
_EMBEDDED_CANDIDATES = (
    "metadata/thumbnail.png",
    "metadata/plate_1.png",
    "auxiliaries/.thumbnails/thumbnail_middle.png",
    "auxiliaries/.thumbnails/thumbnail_3mf.png",
)


def get_thumbnail(path: str, size: int = 256) -> Image.Image | None:
    """Miniatura do arquivo cabendo em size x size px (proporção mantida).

    None se nem o Windows nem o próprio arquivo tiverem uma imagem.
    """
    # O Shell só aceita caminho absoluto com "\" ("C:/x/y.stl" é recusado)
    path = os.path.abspath(path)
    image = _windows_thumbnail(path, size) if sys.platform == "win32" else None
    if image is None and path.lower().endswith(".3mf"):
        image = _embedded_3mf_thumbnail(path)
    if image is None:
        return None
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image


# ------------------------------------------------------- miniatura embutida

def _embedded_3mf_thumbnail(path: str) -> Image.Image | None:
    """Imagem gravada pelo fatiador dentro do .3mf (um .zip)."""
    try:
        with zipfile.ZipFile(path) as package:
            names = {name.lower(): name for name in package.namelist()}
            name = _package_thumbnail(package, names)
            if name is None:
                name = next((names[c] for c in _EMBEDDED_CANDIDATES if c in names), None)
            if name is None or package.getinfo(name).file_size > _MAX_EMBEDDED_BYTES:
                return None
            data = package.read(name)
        image = Image.open(io.BytesIO(data))
        image.load()
        return image
    except Exception:  # arquivo corrompido ou fora do padrão: fica sem miniatura
        return None


def _package_thumbnail(package: zipfile.ZipFile, names: dict[str, str]) -> str | None:
    """Nome da miniatura declarada em _rels/.rels, se existir no pacote."""
    rels = names.get("_rels/.rels")
    if rels is None or package.getinfo(rels).file_size > 1024 * 1024:
        return None
    for relationship in ElementTree.fromstring(package.read(rels)):
        if relationship.get("Type") == _THUMBNAIL_RELATIONSHIP:
            target = posixpath.normpath(relationship.get("Target", "").lstrip("/"))
            if target.lower() in names:
                return names[target.lower()]
    return None


# ----------------------------------------------------------- Windows Shell

def _windows_thumbnail(path: str, size: int) -> Image.Image | None:
    """Pede ao Windows a miniatura (nunca o ícone do tipo de arquivo)."""
    _ensure_com()
    factory = ctypes.c_void_p()
    try:
        _SHCreateItemFromParsingName(path, None, ctypes.byref(_IID_IShellItemImageFactory),
                                     ctypes.byref(factory))
    except OSError:
        return None  # caminho inválido ou inacessível
    # Métodos pela posição na vtable: IUnknown (0-2) e GetImage (3)
    vtable = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    try:
        hbitmap = _HBITMAP()
        try:
            _GetImage(vtable[3])(factory, _SIZE(size, size),
                                 _SIIGBF_THUMBNAILONLY | _SIIGBF_BIGGERSIZEOK,
                                 ctypes.byref(hbitmap))
        except OSError:
            return None  # o tipo não tem gerador de miniaturas, ou ele falhou
        try:
            return _hbitmap_to_image(hbitmap)
        finally:
            _DeleteObject(hbitmap)
    finally:
        _Release(vtable[2])(factory)


def _hbitmap_to_image(hbitmap) -> Image.Image | None:
    info = _BITMAP()
    if not _GetObjectW(hbitmap, ctypes.sizeof(info), ctypes.byref(info)):
        return None
    width, height = info.bmWidth, abs(info.bmHeight)
    if width <= 0 or height <= 0:
        return None

    header = _BITMAPINFO()
    header.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    header.bmiHeader.biWidth = width
    header.bmiHeader.biHeight = -height  # negativo: linhas de cima para baixo
    header.bmiHeader.biPlanes = 1
    header.bmiHeader.biBitCount = 32     # BGRA, 4 bytes por pixel
    pixels = ctypes.create_string_buffer(width * height * 4)
    dc = _CreateCompatibleDC(None)
    try:
        copied = _GetDIBits(dc, hbitmap, 0, height, pixels, ctypes.byref(header), _DIB_RGB_COLORS)
    finally:
        _DeleteDC(dc)
    if copied != height:
        return None

    # Miniaturas vêm com alfa direto (não pré-multiplicado), ao contrário dos ícones
    image = Image.frombytes("RGBA", (width, height), pixels.raw, "raw", "BGRA")
    if info.bmBitsPixel < 32 or image.getchannel("A").getextrema()[1] == 0:
        # Sem canal alfa (alguns geradores deixam o alfa zerado): imagem opaca
        image.putalpha(255)
    return image


_com = threading.local()


def _ensure_com() -> None:
    """Inicializa o COM nesta thread (uma vez). STA, como o Explorer; se a
    thread já usa outro modelo (RPC_E_CHANGED_MODE), o Shell funciona igual."""
    if not getattr(_com, "ready", False):
        _CoInitializeEx(None, _COINIT_APARTMENTTHREADED | _COINIT_DISABLE_OLE1DDE)
        _com.ready = True


if sys.platform == "win32":
    from ctypes import wintypes

    _COINIT_APARTMENTTHREADED = 0x2
    _COINIT_DISABLE_OLE1DDE = 0x4
    _SIIGBF_BIGGERSIZEOK = 0x01   # aceita a do cache maior que o pedido (o Pillow reduz)
    _SIIGBF_THUMBNAILONLY = 0x08  # sem miniatura, falha em vez de devolver o ícone
    _DIB_RGB_COLORS = 0
    _HBITMAP = wintypes.HBITMAP

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class _SIZE(ctypes.Structure):
        _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

    class _BITMAP(ctypes.Structure):
        _fields_ = [("bmType", wintypes.LONG), ("bmWidth", wintypes.LONG),
                    ("bmHeight", wintypes.LONG), ("bmWidthBytes", wintypes.LONG),
                    ("bmPlanes", wintypes.WORD), ("bmBitsPixel", wintypes.WORD),
                    ("bmBits", ctypes.c_void_p)]

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    class _BITMAPINFO(ctypes.Structure):
        # Espaço para as 3 máscaras que o GetDIBits pode escrever após o cabeçalho
        _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    _IID_IShellItemImageFactory = _GUID.from_buffer_copy(
        uuid.UUID("bcc18b79-ba16-442f-80c4-8a59c30c463b").bytes_le)

    # Instâncias próprias das DLLs: os protótipos abaixo não afetam o
    # ctypes.windll compartilhado com outras bibliotecas (ex.: pystray)
    _shell32 = ctypes.WinDLL("shell32")
    _ole32 = ctypes.WinDLL("ole32")
    _gdi32 = ctypes.WinDLL("gdi32")

    _SHCreateItemFromParsingName = _shell32.SHCreateItemFromParsingName
    _SHCreateItemFromParsingName.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p,
                                             ctypes.POINTER(_GUID),
                                             ctypes.POINTER(ctypes.c_void_p)]
    _SHCreateItemFromParsingName.restype = ctypes.HRESULT  # erro vira OSError

    _CoInitializeEx = _ole32.CoInitializeEx
    _CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    _CoInitializeEx.restype = ctypes.c_long  # S_FALSE e RPC_E_CHANGED_MODE não são erro aqui

    _GetObjectW = _gdi32.GetObjectW
    _GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
    _GetObjectW.restype = ctypes.c_int

    _GetDIBits = _gdi32.GetDIBits
    _GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                           ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    _GetDIBits.restype = ctypes.c_int

    _CreateCompatibleDC = _gdi32.CreateCompatibleDC
    _CreateCompatibleDC.argtypes = [wintypes.HDC]
    _CreateCompatibleDC.restype = wintypes.HDC

    _DeleteDC = _gdi32.DeleteDC
    _DeleteDC.argtypes = [wintypes.HDC]
    _DeleteDC.restype = wintypes.BOOL

    _DeleteObject = _gdi32.DeleteObject
    _DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _DeleteObject.restype = wintypes.BOOL

    # Protótipos dos métodos COM (o 1º argumento é o próprio objeto)
    _Release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
    _GetImage = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, _SIZE, ctypes.c_int,
                                   ctypes.POINTER(wintypes.HBITMAP))
