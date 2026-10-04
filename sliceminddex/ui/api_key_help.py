"""Ajuda com a API Key do Gemini, para quem nunca ouviu falar dela.

    ApiKeyRequiredDialog  aviso ao iniciar o monitoramento sem a chave;
                          "Adicionar API" leva ao campo nas Configurações
    ApiTutorialWindow     "Como obter sua API Key": textos, link para o
                          Google AI Studio e o passo a passo animado (GIF)
"""

import sys
import tkinter
import webbrowser

import customtkinter as ctk

from sliceminddex.config import API_TUTORIAL_GIF, APP_ICON, APP_NAME, GEMINI_API_KEY_URL
from sliceminddex.locales import t
from sliceminddex.ui import theme
from sliceminddex.ui.widgets import GifPlayer, WrapLabel, ghost_button


class _HelpWindow(ctk.CTkToplevel):
    """Base das duas janelas: ícone do app, fundo do tema e posição sobre
    a janela principal."""

    WIDTH = 520
    MARGIN = 28  # margem lateral da janela

    def __init__(self, app, title: str) -> None:
        super().__init__(app)
        self.app = app
        self.title(f"{APP_NAME} — {title}")
        if sys.platform == "win32" and APP_ICON.is_file():
            # Antes dos 200 ms em que o CustomTkinter poria o ícone padrão dele
            self.iconbitmap(str(APP_ICON))
        self.resizable(False, False)
        self.configure(fg_color=theme.WINDOW_BG)
        self.transient(app)  # sempre na frente da janela principal

    def _place(self) -> None:
        """Centraliza sobre a janela principal, na altura que o conteúdo pede."""
        self.update_idletasks()
        scale = self._get_window_scaling()
        height = round(self.winfo_reqheight() / scale)
        width_px, height_px = round(self.WIDTH * scale), round(height * scale)
        parent = self.app
        x = parent.winfo_rootx() + (parent.winfo_width() - width_px) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height_px) // 3
        x = min(max(0, x), self.winfo_screenwidth() - width_px)
        y = min(max(0, y), self.winfo_screenheight() - height_px)
        self.geometry(f"{self.WIDTH}x{height}+{x}+{y}")  # o CTk escala só largura e altura

    def _header(self, parent, emoji: str, title: str) -> ctk.CTkFrame:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid_columnconfigure(1, weight=1)
        icon = self.app.icons.get(emoji, 40)
        ctk.CTkLabel(header, text="" if icon else emoji, image=icon,
                     font=ctk.CTkFont(family="Segoe UI Emoji", size=30)).grid(
            row=0, column=0, padx=(0, 14))
        WrapLabel(header, text=title, font=theme.font(20, "bold"), text_color=theme.TEXT,
                  wraplength=self.text_width(54)).grid(row=0, column=1, sticky="ew")
        return header

    def text_width(self, inset: int = 0) -> int:
        """Largura do texto dentro da janela (descontado `inset`). Passada já
        na criação, a altura que a janela pede sai certa sem esperar o
        texto se ajustar à largura real."""
        return self.WIDTH - 2 * self.MARGIN - inset - 6

    def bring_to_front(self) -> None:
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()


class ApiKeyRequiredDialog(_HelpWindow):
    """Aviso modal: falta a API Key para o monitoramento começar."""

    WIDTH = 500

    def __init__(self, app) -> None:
        super().__init__(app, t("apikey.title"))
        self.grid_columnconfigure(0, weight=1)
        self._header(self, "🔑", t("apikey.title")).grid(
            row=0, column=0, sticky="ew", padx=self.MARGIN, pady=(26, 0))
        WrapLabel(self, text=t("apikey.message"), font=theme.font(14), text_color=theme.TEXT,
                  wraplength=self.text_width()).grid(row=1, column=0, sticky="ew",
                                                    padx=self.MARGIN,
                                              pady=(14, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=self.MARGIN, pady=(24, 24))
        buttons.grid_columnconfigure(0, weight=1)
        ghost_button(buttons, t("apikey.later"), self._close, height=40, width=120).grid(
            row=0, column=0, sticky="w")
        self.add_button = ctk.CTkButton(
            buttons, text=t("apikey.add"), height=42, width=190, font=theme.font(14, "bold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_ACCENT, command=self._add)
        self.add_button.grid(row=0, column=1, sticky="e")

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _e: self._close())
        self.bind("<Return>", lambda _e: self._add())
        self._place()
        self.bring_to_front()
        self.grab_set()  # modal: a janela principal espera a resposta

    def _add(self) -> None:
        self._close()
        self.app.open_api_key_settings()

    def _close(self) -> None:
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()


class ApiTutorialWindow(_HelpWindow):
    """Como obter a API Key: grátis, onde gerar, cuidado com o segredo e o GIF."""

    WIDTH = 640
    MARGIN = 32
    CARD_PAD = 20   # margem do texto dentro do card
    GIF_PAD = 8     # borda do quadro em volta do GIF
    GIF_MAX = (WIDTH - 2 * MARGIN - 2 * GIF_PAD, 330)  # largura útil da janela

    def __init__(self, app) -> None:
        super().__init__(app, t("tutorial.title"))
        self.grid_columnconfigure(0, weight=1)
        self._header(self, "🔑", t("tutorial.title")).grid(
            row=0, column=0, sticky="ew", padx=self.MARGIN, pady=(26, 0))

        card = ctk.CTkFrame(self, **theme.CARD)
        card.grid(row=1, column=0, sticky="ew", padx=self.MARGIN, pady=(18, 0))
        wrap = self.text_width(2 * self.CARD_PAD)
        card.grid_columnconfigure(0, weight=1)
        WrapLabel(card, text=f"✅  {t('tutorial.free')}", font=theme.font(15, "bold"),
                  text_color=theme.NAV_ACTIVE_TEXT, wraplength=wrap).grid(
            row=0, column=0, sticky="ew", padx=self.CARD_PAD, pady=(16, 0))
        WrapLabel(card, text=t("tutorial.visit"), font=theme.font(13),
                  text_color=theme.TEXT, wraplength=wrap).grid(
            row=1, column=0, sticky="ew", padx=self.CARD_PAD,
                                              pady=(8, 0))
        ctk.CTkButton(card, text=f"{t('tutorial.open_site')}  ↗", height=40,
                      font=theme.font(14, "bold"), fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                      command=lambda: webbrowser.open(GEMINI_API_KEY_URL)).grid(
            row=2, column=0, sticky="w", padx=self.CARD_PAD, pady=(12, 0))
        WrapLabel(card, text=t("tutorial.warning"), font=theme.font(13, "bold"),
                  text_color=theme.WARNING_TEXT, wraplength=wrap).grid(
            row=3, column=0, sticky="ew", padx=self.CARD_PAD, pady=(14, 16))

        # Passo a passo animado, num quadro com o fundo das miniaturas
        frame = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.THUMB_BG)
        frame.grid(row=2, column=0, sticky="ew", padx=self.MARGIN, pady=(14, 0))
        frame.grid_columnconfigure(0, weight=1)
        self.player = GifPlayer(frame, API_TUTORIAL_GIF, self.GIF_MAX,
                                missing_text=t("tutorial.no_animation"),
                                font=theme.font(12), text_color=theme.TEXT_MUTED)
        self.player.grid(row=0, column=0, padx=self.GIF_PAD, pady=self.GIF_PAD)

        ghost_button(self, t("tutorial.close"), self.destroy, height=38, width=120).grid(
            row=3, column=0, sticky="e", padx=self.MARGIN, pady=(14, 22))
        self.bind("<Escape>", lambda _e: self.destroy())
        self._place()
        self.bring_to_front()

    def show(self) -> None:
        """Traz de volta para a frente (o "?" clicado com a janela já aberta)."""
        self.deiconify()
        self.bring_to_front()
