"""Autodiagnóstico: confere, de dentro do .exe, se nada ficou de fora.

    SliceMindDex.exe --self-test relatorio.txt

Testa cada peça que o app usa (bibliotecas, arquivos embutidos, backends
nativos do Windows, certificados HTTPS) e grava um relatório. Código de saída
0 = tudo certo. O build.ps1 roda isto após cada build e falha se algo faltar.
Não abre janela nem mexe nas configurações do usuário.
"""

import os
import sys
import traceback


def _checks():
    """(nome, função) — cada função retorna um detalhe ou lança exceção."""

    def interface():
        import tkinter
        import customtkinter
        themes = os.path.join(os.path.dirname(customtkinter.__file__), "assets", "themes")
        if not os.path.isfile(os.path.join(themes, "green.json")):
            raise FileNotFoundError("temas do CustomTkinter não embutidos")
        return f"Tcl/Tk {tkinter.Tcl().eval('info patchlevel')}, CustomTkinter {customtkinter.__version__}"

    def theme_detection():
        import darkdetect
        return f"tema do Windows: {darkdetect.theme()}"

    def images():
        from PIL import Image, features
        if not features.check("freetype2"):
            raise RuntimeError("Pillow sem FreeType (ícones coloridos)")
        return f"Pillow com FreeType {features.version('freetype2')}"

    def app_icon():
        from PIL import Image
        from sliceminddex.config import APP_ICON
        with Image.open(APP_ICON) as icon:
            return f"{APP_ICON.name}: {len(icon.ico.sizes())} tamanhos"

    def emoji_font():
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguiemj.ttf")
        if not os.path.isfile(path):
            raise FileNotFoundError("Segoe UI Emoji ausente (ícones viram texto)")
        return "Segoe UI Emoji presente"

    def thumbnails():
        import tempfile
        from PIL import Image
        from sliceminddex.core.thumbnail_helper import get_thumbnail
        from sliceminddex.ui.icons import model_file_icon
        model_file_icon(".stl", dark=True)  # ícone de quando não há miniatura
        if sys.platform != "win32":
            return "fora do Windows: só o ícone genérico"
        # Um PNG sempre tem miniatura no Windows: testa ctypes + COM + GDI
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            path = os.path.join(folder, "sliceminddex-self-test.png")
            Image.new("RGB", (96, 64), (0, 174, 66)).save(path)
            image = get_thumbnail(path, 48)
        if image is None:
            raise RuntimeError("o Windows não devolveu a miniatura de um PNG")
        color = image.getpixel((image.width // 2, image.height // 2))
        if any(abs(a - b) > 4 for a, b in zip(color, (0, 174, 66, 255))):
            raise RuntimeError(f"cores trocadas na conversão da miniatura: {color}")
        return f"Windows Shell ok ({image.width}x{image.height})"

    def api_tutorial():
        from PIL import Image
        from sliceminddex.config import API_TUTORIAL_GIF
        if not API_TUTORIAL_GIF.is_file():
            return "sem docs/api_tutorial.gif: a janela de ajuda mostra só os textos"
        with Image.open(API_TUTORIAL_GIF) as gif:
            gif.seek(0)
            gif.convert("RGBA")  # o primeiro quadro decodifica
            return f"GIF {gif.size[0]}x{gif.size[1]}, {getattr(gif, 'n_frames', 1)} quadros"

    def folder_watcher():
        from watchdog.observers import Observer
        name = Observer.__name__
        # Sem o backend nativo o Watchdog cairia, sem avisar, no modo de varredura lenta
        if sys.platform == "win32" and name != "WindowsApiObserver":
            raise RuntimeError(f"Watchdog usando {name}, não o backend do Windows")
        return name

    def tray():
        import pystray
        backend = pystray.Icon.__module__
        if sys.platform == "win32" and backend != "pystray._win32":
            raise RuntimeError(f"pystray usando {backend}")
        return backend

    def database():
        import sqlite3
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x TEXT)")
        return f"SQLite {sqlite3.sqlite_version}"

    def gemini_sdk():
        from google import genai
        from google.genai import types  # noqa: F401
        import pydantic_core  # noqa: F401
        from sliceminddex.core import organizer  # noqa: F401 (schema, prompt, cliente)
        return f"google-genai {genai.__version__}"

    def https_certificates():
        import certifi
        import httpx
        if not os.path.isfile(certifi.where()):
            raise FileNotFoundError("certificados (cacert.pem) não embutidos")
        # Só o aperto de mão TLS com a API do Gemini (sem chave: a resposta é erro, tudo bem)
        try:
            response = httpx.get("https://generativelanguage.googleapis.com/", timeout=10)
        except httpx.ConnectError as exc:
            if "CERTIFICATE" in str(exc).upper():
                raise
            return f"cacert.pem ok; sem internet para testar ({exc.__class__.__name__})"
        return f"TLS ok com a API do Gemini (HTTP {response.status_code})"

    def translations():
        from sliceminddex import locales
        sizes = {code: len(table) for code, table in locales.STRINGS.items()}
        if len(set(sizes.values())) != 1:
            raise RuntimeError(f"traduções incompletas: {sizes}")
        return ", ".join(f"{code}={n}" for code, n in sizes.items())

    def interface_modules():
        from sliceminddex.ui import app  # noqa: F401 (todas as telas)
        return "telas e serviço carregados"

    return [
        ("Interface (Tk/CustomTkinter)", interface),
        ("Detecção de tema", theme_detection),
        ("Imagens (Pillow)", images),
        ("Ícone do app", app_icon),
        ("Fonte de emojis", emoji_font),
        ("Miniaturas (Windows Shell)", thumbnails),
        ("Tutorial da API Key (GIF)", api_tutorial),
        ("Monitor de pastas (Watchdog)", folder_watcher),
        ("Bandeja (pystray)", tray),
        ("Banco de dados (SQLite)", database),
        ("SDK do Gemini", gemini_sdk),
        ("HTTPS / certificados", https_certificates),
        ("Traduções", translations),
        ("Módulos da interface", interface_modules),
    ]


def run(report_path: str) -> int:
    lines, failures = [], 0
    for name, check in _checks():
        try:
            lines.append(f"[OK]    {name}: {check()}")
        except Exception as exc:
            failures += 1
            lines.append(f"[FALHA] {name}: {exc}")
            lines.append("        " + traceback.format_exc().strip().replace("\n", "\n        "))
    lines.append(f"\n{'Tudo certo' if not failures else f'{failures} falha(s)'} "
                 f"({'empacotado' if getattr(sys, 'frozen', False) else 'código-fonte'})")
    with open(report_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    return 1 if failures else 0
