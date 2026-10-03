"""Assistente de primeira execução: escolher as pastas antes de usar o app.

Abre como janela modal, com a janela principal ainda escondida. Só fecha
pelo "Concluir" (pastas válidas e salvas) ou por "Sair do SliceMind DEX": o X da
janela não pula a configuração.
"""

import os
import sys
import tkinter
from tkinter import filedialog

import customtkinter as ctk
from platformdirs import user_downloads_dir

from sliceminddex.config import APP_ICON, APP_NAME, DEFAULT_DEST_DIR, with_prints_folder
from sliceminddex.locales import t
from sliceminddex.ui import theme
from sliceminddex.ui.widgets import WrapLabel


def _suggested_downloads() -> str:
    path = user_downloads_dir()
    return os.path.normpath(path) if os.path.isdir(path) else ""


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


class OnboardingDialog(ctk.CTkToplevel):
    WIDTH, HEIGHT = 640, 560

    def __init__(self, app) -> None:
        super().__init__(app)
        self.app = app
        self.completed = False
        self.title(f"{APP_NAME} — {t('onb.window_title')}")
        if sys.platform == "win32" and APP_ICON.is_file():
            # Antes dos 200 ms em que o CustomTkinter poria o ícone padrão dele
            self.iconbitmap(str(APP_ICON))
        self.resizable(False, False)
        self.configure(fg_color=theme.WINDOW_BG)
        self.protocol("WM_DELETE_WINDOW", self._block_close)

        # Origem: sugere a pasta Downloads; destino: já vem com o padrão do app
        self.source_var = ctk.StringVar(value=app.source_var.get() or _suggested_downloads())
        self.dest_var = ctk.StringVar(value=app.dest_var.get() or str(DEFAULT_DEST_DIR))
        self._build()
        self._center()

        # Modal: fica na frente e prende o foco até concluir
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.grab_set()
        self.focus_force()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew", padx=32, pady=(28, 0))
        body.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        logo = self.app.icons.app_icon(56)
        if logo:
            ctk.CTkLabel(header, text="", image=logo).grid(row=0, column=0, rowspan=2,
                                                           padx=(0, 16))
        ctk.CTkLabel(header, text=t("onb.title"), font=theme.font(24, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=1, sticky="w")
        WrapLabel(header, text=t("onb.subtitle"), font=theme.font(13),
                  text_color=theme.TEXT_MUTED).grid(row=1, column=1, sticky="ew")

        card = ctk.CTkFrame(body, **theme.CARD)
        card.grid(row=1, column=0, sticky="ew", pady=(22, 0))
        card.grid_columnconfigure(0, weight=1)
        self._folder_field(card, 0, t("onb.source"), t("set.source_hint"), self.source_var)
        self._folder_field(card, 3, t("onb.dest"), t("set.dest_hint"), self.dest_var)
        # Aviso crítico logo abaixo do destino
        WrapLabel(card, text=f"⚠  {t('onb.warning')}", font=theme.font(12, "bold"),
                  text_color=theme.STATUS_COLORS["stopping"]).grid(
            row=6, column=0, sticky="ew", padx=20, pady=(10, 18))

        self.error = WrapLabel(body, text="", font=theme.font(12, "bold"),
                               text_color=theme.DANGER)
        self.error.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew", padx=32, pady=(8, 26))
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(buttons, text=t("onb.exit"), height=40, width=150,
                      fg_color="transparent", border_width=1,
                      border_color=theme.CARD_BORDER, hover_color=theme.NAV_HOVER,
                      text_color=theme.TEXT_MUTED, font=theme.font(13),
                      command=self._exit).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(buttons, text=t("onb.finish"), height=44, width=180,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ON_ACCENT, font=theme.font(15, "bold"),
                      command=self._finish).grid(row=0, column=1, sticky="e")

    def _folder_field(self, card, row: int, label: str, hint: str,
                      var: ctk.StringVar) -> None:
        ctk.CTkLabel(card, text=label, font=theme.font(14, "bold"), text_color=theme.TEXT,
                     anchor="w").grid(row=row, column=0, sticky="w", padx=20, pady=(18, 0))
        WrapLabel(card, text=hint, font=theme.font(12), text_color=theme.TEXT_MUTED).grid(
            row=row + 1, column=0, sticky="ew", padx=20)
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.grid(row=row + 2, column=0, sticky="ew", padx=20, pady=(6, 0))
        line.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(line, textvariable=var, height=38, font=theme.font(13)).grid(
            row=0, column=0, sticky="ew")
        ctk.CTkButton(line, text=t("set.browse"), width=112, height=38, font=theme.font(13),
                      command=lambda: self._browse(var)).grid(row=0, column=1, padx=(8, 0))

    def _center(self) -> None:
        scale = self._get_window_scaling()
        width, height = int(self.WIDTH * scale), int(self.HEIGHT * scale)
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 3)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    # -------------------------------------------------------------- ações

    def _browse(self, var: ctk.StringVar) -> None:
        current = var.get().strip()
        folder = filedialog.askdirectory(parent=self,
                                         initialdir=current if os.path.isdir(current) else None)
        if folder:
            var.set(os.path.normpath(folder))

    def _finish(self) -> None:
        source = self.source_var.get().strip()
        if not source or not os.path.isdir(source):
            self._show_error(t("onb.error_source"))
            return
        dest = self.dest_var.get().strip()
        if not dest:
            self._show_error(t("onb.error_dest", path="—"))
            return
        # Mesma regra das Configurações: a árvore da IA fica sempre em <pasta>/PRINTS
        dest = with_prints_folder(os.path.normpath(dest))
        base = os.path.dirname(dest)
        if not os.path.isdir(base) and not _same_path(dest, str(DEFAULT_DEST_DIR)):
            self._show_error(t("onb.error_dest", path=base))
            return
        try:
            os.makedirs(dest, exist_ok=True)
        except OSError as exc:
            self._show_error(t("onb.error_create", path=dest, error=exc))
            return

        self.app.source_var.set(os.path.normpath(source))
        self.app.dest_var.set(dest)
        self.app.commit_folder("pasta_origem")
        self.app.commit_folder("pasta_destino")
        self.completed = True
        self._close()

    def _exit(self) -> None:
        self.completed = False
        self._close()

    def _block_close(self) -> None:
        self.bell()
        self._show_error(t("onb.must_finish"))

    def _show_error(self, text: str) -> None:
        self.error.configure(text=text)

    def _close(self) -> None:
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()
