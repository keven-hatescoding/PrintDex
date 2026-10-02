"""Menu lateral: logo, navegação entre as telas e status do monitoramento.

Em janelas estreitas (ex.: monitor em pé, 9:16) o menu vira uma coluna só
de ícones, deixando o espaço para o conteúdo.
"""

import customtkinter as ctk

from printdex import RELEASE
from printdex.config import APP_NAME
from printdex.locales import t
from printdex.ui import theme
from printdex.ui.widgets import WrapLabel

# (tela, ícone, chave do texto). Os ícones são emojis desenhados pelo Tk em
# monocromático, na cor do texto do botão.
NAV_ITEMS = (
    ("dashboard", "📊", "nav.dashboard"),
    ("library", "📚", "nav.library"),
    ("calculator", "🧮", "nav.calculator"),
    ("settings", "⚙", "nav.settings"),
)
EXIT_ICON = "⏻"


class Sidebar(ctk.CTkFrame):
    WIDE = 232
    NARROW = 76

    def __init__(self, master, app) -> None:
        super().__init__(master, width=self.WIDE, corner_radius=0,
                         fg_color=theme.SIDEBAR_BG)
        self.app = app
        self.compact = False
        self._active = ""
        self._state = "stopped"
        self.grid_propagate(False)  # largura fixa, independente do conteúdo
        self.grid_columnconfigure(0, weight=1)
        footer = 3 + len(NAV_ITEMS)  # logo, slogan e botões; depois um espaço elástico
        self.grid_rowconfigure(footer - 1, weight=1)

        logo = app.icons.app_icon(34) or app.icons.get("🧊", 30)  # sem o .ico, o emoji
        self.logo = ctk.CTkLabel(self, text=f"  {APP_NAME}", image=logo,
                                 compound="left", font=theme.font(21, "bold"),
                                 text_color=theme.TEXT, anchor="w")
        self.logo.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 2))
        self.tagline = WrapLabel(self, text=t("app.tagline"), font=theme.font(12),
                                 text_color=theme.TEXT_MUTED)
        self.tagline.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 24))

        self.buttons: dict[str, ctk.CTkButton] = {}
        for row, (view, _icon, _key) in enumerate(NAV_ITEMS, start=2):
            button = ctk.CTkButton(
                self, height=44, corner_radius=10, anchor="w",
                font=theme.font(14), fg_color="transparent",
                hover_color=theme.NAV_HOVER, text_color=theme.TEXT,
                command=lambda name=view: app.show_view(name),
            )
            button.grid(row=row, column=0, sticky="ew", padx=12, pady=3)
            self.buttons[view] = button

        # O X da janela só esconde na bandeja: este botão encerra de vez
        self.exit_button = ctk.CTkButton(
            self, height=38, corner_radius=10, anchor="w", font=theme.font(13),
            fg_color="transparent", hover_color=theme.NAV_HOVER,
            text_color=theme.TEXT_MUTED, command=app.quit_app,
        )
        self.exit_button.grid(row=footer, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.status = ctk.CTkLabel(self, text="", font=theme.font(12, "bold"), anchor="w")
        self.status.grid(row=footer + 1, column=0, sticky="ew", padx=22)
        self.version = ctk.CTkLabel(self, text=f"v{RELEASE}", font=theme.font(11),
                                    text_color=theme.TEXT_MUTED, anchor="w")
        self.version.grid(row=footer + 2, column=0, sticky="ew", padx=22, pady=(0, 18))
        self._update_texts()

    def set_active(self, view: str) -> None:
        self._active = view
        for name, button in self.buttons.items():
            active = name == view
            button.configure(
                fg_color=theme.NAV_ACTIVE if active else "transparent",
                text_color=theme.NAV_ACTIVE_TEXT if active else theme.TEXT,
                font=theme.font(14, "bold" if active else "normal"),
            )

    def set_status(self, state: str) -> None:
        self._state = state
        self.status.configure(text_color=theme.STATUS_COLORS[state])
        self._update_texts()

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        self.configure(width=self.NARROW if compact else self.WIDE)
        if compact:
            self.tagline.grid_remove()
        else:
            self.tagline.grid()
        self._update_texts()

    def _update_texts(self) -> None:
        compact = self.compact
        anchor = "center" if compact else "w"
        self.logo.configure(text="" if compact else f"  {APP_NAME}", anchor=anchor)
        for view, icon, key in NAV_ITEMS:
            self.buttons[view].configure(
                text=icon if compact else f"{icon}    {t(key)}", anchor=anchor)
        self.exit_button.configure(
            text=EXIT_ICON if compact else f"{EXIT_ICON}    {t('tray.exit')}", anchor=anchor)
        status = t(f"status.{self._state}")
        self.status.configure(text="●" if compact else f"●  {status}", anchor=anchor)
        self.version.configure(anchor=anchor)
        # grid() (e não grid_configure) para o CustomTkinter aplicar a escala de DPI
        self.logo.grid(padx=0 if compact else 20)
        self.status.grid(padx=0 if compact else 22)
        self.version.grid(padx=0 if compact else 22)
