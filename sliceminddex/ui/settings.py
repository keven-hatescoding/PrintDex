"""Tela Configurações: idioma, tema, pastas, API Key e informações do app.

Tudo é salvo no SQLite assim que muda (sem botão "aplicar").
"""

import customtkinter as ctk

from sliceminddex import RELEASE
from sliceminddex.config import APP_DATA_DIR, GEMINI_MODEL, THEMES
from sliceminddex.core.calculator import CURRENCIES, currency_symbol
from sliceminddex.locales import LANGUAGES, get_language, t
from sliceminddex.ui import theme
from sliceminddex.ui.widgets import Section, Tooltip, ViewHeader, WrapLabel, ghost_button


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._folder_widgets: list[ctk.CTkBaseClass] = []
        self._key_visible = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ViewHeader(self, t("set.title"), t("set.subtitle")).grid(
            row=0, column=0, sticky="ew", pady=(0, 18))

        # Rolagem: em janelas baixas o formulário rola em vez de ser cortado
        body = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        self._body = body
        self._build_appearance(body).grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self._build_folders(body).grid(row=1, column=0, sticky="ew", pady=(0, 14))
        self._ai_section = self._build_ai(body)
        self._ai_section.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self._build_about(body).grid(row=3, column=0, sticky="ew", pady=(0, 6))

    def _build_appearance(self, parent) -> Section:
        section = Section(parent, t("set.appearance"))

        row = section.field(t("set.language"))
        self.language_menu = ctk.CTkOptionMenu(
            row, values=list(LANGUAGES.values()), command=self._on_language,
            width=220, height=34, font=theme.font(13), dropdown_font=theme.font(13))
        self.language_menu.set(LANGUAGES[get_language()])
        self.language_menu.grid(row=0, column=0, sticky="w")

        # Moeda da Calculadora: muda rótulos e valores de lá na hora
        row = section.field(t("set.currency"))
        self._currencies = {f"{code} ({currency_symbol(code)})": code for code in CURRENCIES}
        self.currency_menu = ctk.CTkOptionMenu(
            row, values=list(self._currencies),
            command=lambda name: self.app.set_currency(self._currencies[name]),
            width=220, height=34, font=theme.font(13), dropdown_font=theme.font(13))
        self.currency_menu.set(next(name for name, code in self._currencies.items()
                                    if code == self.app.currency))
        self.currency_menu.grid(row=0, column=0, sticky="w")

        row = section.field(t("set.theme"), t("set.theme_hint"))
        self._theme_names = {t(f"theme.{mode}"): mode for mode in THEMES}
        self.theme_buttons = ctk.CTkSegmentedButton(
            row, values=list(self._theme_names), command=self._on_theme,
            height=34, font=theme.font(13))
        self.theme_buttons.set(t(f"theme.{self.app.theme}"))
        self.theme_buttons.grid(row=0, column=0, sticky="w")
        return section

    def _build_folders(self, parent) -> Section:
        section = Section(parent, t("set.folders"))
        self.lock_note = WrapLabel(section, text=f"🔒  {t('set.locked')}", font=theme.font(12),
                                   text_color=theme.STATUS_COLORS["stopping"])
        section.add(self.lock_note, pady=(8, 0))
        self.lock_note.grid_remove()

        fields = (("pasta_origem", self.app.source_var, "set.source_hint"),
                  ("pasta_destino", self.app.dest_var, "set.dest_hint"))
        for field, var, hint in fields:
            row = section.field(t(f"field.{field}"), t(hint))
            entry = ctk.CTkEntry(row, textvariable=var, height=36, font=theme.font(13))
            entry.grid(row=0, column=0, sticky="ew")
            # Caminho digitado à mão é salvo ao pressionar Enter ou sair do campo
            entry.bind("<Return>", lambda _e, f=field: self.app.commit_folder(f), add="+")
            entry.bind("<FocusOut>", lambda _e, f=field: self.app.commit_folder(f), add="+")
            browse = ctk.CTkButton(row, text=t("set.browse"), width=112, height=36,
                                   font=theme.font(13),
                                   command=lambda f=field: self.app.browse_folder(f))
            browse.grid(row=0, column=1, padx=(8, 0))
            self._folder_widgets += [entry, browse]
        return section

    def _build_ai(self, parent) -> Section:
        section = Section(parent, t("set.ai"))
        row = section.field(t("field.api_key"), t("set.api_hint"))
        self.key_entry = ctk.CTkEntry(row, textvariable=self.app.api_key_var, show="•",
                                      height=36, font=theme.font(13))
        self.key_entry.grid(row=0, column=0, sticky="ew")
        self.key_entry.bind("<Return>", lambda _e: self.app.save_api_key(), add="+")
        # "?" redondo e em destaque: abre o passo a passo de como conseguir a chave
        self.help_button = ctk.CTkButton(
            row, text="?", width=36, height=36, corner_radius=18,
            font=theme.font(17, "bold"), fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
            command=self.app.open_api_tutorial)
        self.help_button.grid(row=0, column=1, padx=(8, 0))
        self.help_tip = Tooltip(self.help_button, t("apikey.help"))
        self.show_button = ghost_button(row, t("set.show"), self._toggle_key,
                                        width=92, height=36)
        self.show_button.grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(row, text=t("set.save"), width=92, height=36, font=theme.font(13),
                      command=self.app.save_api_key).grid(row=0, column=3, padx=(8, 0))
        return section

    def focus_api_key(self) -> None:
        """Rola até a API Key, põe o cursor no campo e o destaca por um instante."""
        self.update_idletasks()
        canvas = self._body._parent_canvas
        top = self._ai_section.winfo_y() / max(1, self._body.winfo_height())
        canvas.yview_moveto(max(0.0, top - 0.02))
        self.key_entry.focus_set()
        self.key_entry.configure(border_color=theme.ACCENT, border_width=2)
        self.after(1800, self._unhighlight_key)

    def _unhighlight_key(self) -> None:
        if self.key_entry.winfo_exists():
            # Volta à borda padrão do tema
            self.key_entry.configure(
                border_color=ctk.ThemeManager.theme["CTkEntry"]["border_color"],
                border_width=ctk.ThemeManager.theme["CTkEntry"]["border_width"])

    def _build_about(self, parent) -> Section:
        section = Section(parent, t("set.about"))
        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.grid_columnconfigure(1, weight=1)
        rows = ((t("set.version"), RELEASE),
                (t("set.model"), GEMINI_MODEL),
                (t("set.data_folder"), str(APP_DATA_DIR)))
        for index, (label, value) in enumerate(rows):
            ctk.CTkLabel(grid, text=label, font=theme.font(12), text_color=theme.TEXT_MUTED,
                         anchor="w").grid(row=index, column=0, sticky="nw", padx=(0, 16), pady=3)
            WrapLabel(grid, text=value, font=theme.font(12), text_color=theme.TEXT).grid(
                row=index, column=1, sticky="ew", pady=3)
        section.add(grid, pady=(10, 0))
        return section

    # -------------------------------------------------------------- eventos

    def _on_language(self, display_name: str) -> None:
        code = next(code for code, name in LANGUAGES.items() if name == display_name)
        # Pela janela, depois do callback: trocar o idioma recria esta tela
        self.app.after(10, lambda: self.app.set_language(code))

    def _on_theme(self, display_name: str) -> None:
        self.app.set_theme(self._theme_names[display_name])

    def _toggle_key(self) -> None:
        self._key_visible = not self._key_visible
        self.key_entry.configure(show="" if self._key_visible else "•")
        self.show_button.configure(text=t("set.hide") if self._key_visible else t("set.show"))

    def set_locked(self, locked: bool) -> None:
        """Durante o monitoramento as pastas não podem mudar."""
        for widget in self._folder_widgets:
            widget.configure(state="disabled" if locked else "normal")
        if locked:
            self.lock_note.grid()
        else:
            self.lock_note.grid_remove()
