"""Tela Painel: status e controles do monitoramento, contadores e log."""

import customtkinter as ctk

from sliceminddex.core.service import Stats
from sliceminddex.locales import Msg, t
from sliceminddex.ui import theme
from sliceminddex.ui.widgets import ViewHeader, WrapLabel, ghost_button

LOG_LIMIT = 1000  # linhas mantidas na tela

# Cor de cada mensagem do log; sem entrada aqui, chaves terminadas em
# "error", "not_found" etc. são erro e o resto fica na cor normal
_LOG_LEVELS = {
    "log.success": "ok",
    "log.monitor_started": "ok",
    "log.ai_error": "warn",
    "log.default_dest_error": "warn",
    "log.cancelled": "warn",
    "log.queue_left": "warn",
    "log.rate_hint": "warn",
}
_ERROR_SUFFIXES = ("error", "_not_found", "vanished", "missing", "unavailable")


def _level(msg: Msg) -> str:
    if msg.key in _LOG_LEVELS:
        return _LOG_LEVELS[msg.key]
    return "error" if msg.key.endswith(_ERROR_SUFFIXES) else ""


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # o log fica com a altura que sobrar

        ViewHeader(self, t("dash.title"), t("dash.subtitle")).grid(
            row=0, column=0, sticky="ew", pady=(0, 18))
        self._build_status_card()
        self._build_stats()
        self._build_log()

    # ---------------------------------------------------------------- layout

    def _build_status_card(self) -> None:
        card = ctk.CTkFrame(self, **theme.CARD)
        card.grid(row=1, column=0, sticky="ew")
        # Botões lado a lado, cada um com metade da largura: cabem em qualquer janela
        card.grid_columnconfigure((0, 1), weight=1, uniform="buttons")

        self.status_label = ctk.CTkLabel(card, text="", font=theme.font(20, "bold"), anchor="w")
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(18, 8))

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20)
        info.grid_columnconfigure(1, weight=1)
        self._paths: dict[str, WrapLabel] = {}
        for row, field in enumerate(("pasta_origem", "pasta_destino")):
            ctk.CTkLabel(info, text=t(f"field.{field}"), font=theme.font(12),
                         text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=row, column=0, sticky="nw", padx=(0, 14), pady=3)
            label = WrapLabel(info, text="", font=theme.font(12))
            label.grid(row=row, column=1, sticky="ew", pady=3)
            self._paths[field] = label

        button = dict(height=44, corner_radius=10, font=theme.font(14, "bold"),
                      text_color=theme.ON_ACCENT, text_color_disabled=theme.TEXT_DISABLED)
        self.start_btn = ctk.CTkButton(card, text=f"▶   {t('dash.start')}",
                                       command=self.app.start_monitoring, **button)
        self.start_btn.grid(row=2, column=0, sticky="ew", padx=(20, 6), pady=(16, 20))
        self.stop_btn = ctk.CTkButton(card, text=f"■   {t('dash.stop')}",
                                      command=self.app.stop_monitoring, **button)
        self.stop_btn.grid(row=2, column=1, sticky="ew", padx=(6, 20), pady=(16, 20))

    def _build_stats(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", pady=16)
        self._stats: dict[str, ctk.CTkLabel] = {}
        tiles = (("organized", "dash.stat.organized"), ("queued", "dash.stat.queue"),
                 ("attention", "dash.stat.attention"))
        for column, (name, caption) in enumerate(tiles):
            row.grid_columnconfigure(column, weight=1, uniform="stats")
            tile = ctk.CTkFrame(row, **theme.CARD)
            tile.grid(row=0, column=column, sticky="nsew",
                      padx=(0 if column == 0 else 6, 0 if column == len(tiles) - 1 else 6))
            tile.grid_columnconfigure(0, weight=1)
            value = ctk.CTkLabel(tile, text="0", font=theme.font(30, "bold"), anchor="w")
            value.grid(row=0, column=0, sticky="w", padx=18, pady=(12, 0))
            WrapLabel(tile, text=t(caption), font=theme.font(12),
                      text_color=theme.TEXT_MUTED).grid(
                row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
            self._stats[name] = value

    def _build_log(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bar, text=t("dash.activity"), font=theme.font(16, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=0, sticky="w")
        ghost_button(bar, t("dash.clear"), self.app.clear_log, width=90,
                     height=28, font=theme.font(12)).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(
            self, height=120, wrap="word", font=theme.mono_font(12),
            corner_radius=14, border_width=1, border_color=theme.CARD_BORDER,
            fg_color=theme.CARD_BG, text_color=theme.TEXT, border_spacing=10,
        )
        self.log_box.grid(row=4, column=0, sticky="nsew")
        for tag, color in theme.LOG_COLORS.items():
            self.log_box.tag_config(tag, foreground=color)
        self.log_box.configure(state="disabled")

    # ----------------------------------------------------------- atualização

    def set_state(self, state: str) -> None:
        self.status_label.configure(text=f"●  {t(f'status.{state}')}",
                                    text_color=theme.STATUS_COLORS[state])
        can_start, can_stop = state == "stopped", state == "running"
        self.start_btn.configure(
            state="normal" if can_start else "disabled",
            fg_color=theme.ACCENT if can_start else theme.BUTTON_DISABLED,
            hover_color=theme.ACCENT_HOVER)
        self.stop_btn.configure(
            state="normal" if can_stop else "disabled",
            fg_color=theme.DANGER if can_stop else theme.BUTTON_DISABLED,
            hover_color=theme.DANGER_HOVER)

    def set_stats(self, stats: Stats) -> None:
        attention = stats.unknown + stats.errors
        self._stats["organized"].configure(
            text=str(stats.organized),
            text_color=theme.STATUS_COLORS["running"] if stats.organized else theme.TEXT)
        self._stats["queued"].configure(text=str(stats.queued), text_color=theme.TEXT)
        self._stats["attention"].configure(
            text=str(attention),
            text_color=theme.STATUS_COLORS["stopping"] if attention else theme.TEXT)

    def refresh_paths(self) -> None:
        values = {"pasta_origem": self.app.source_var.get(),
                  "pasta_destino": self.app.dest_var.get()}
        for field, label in self._paths.items():
            path = values[field].strip()
            label.configure(text=path or t("dash.not_set"),
                            text_color=theme.TEXT if path else theme.TEXT_MUTED)

    def render_log(self, records: list[tuple[str, Msg]]) -> None:
        """Redesenha o log inteiro (ex.: depois de trocar o idioma)."""
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        for record in records[-LOG_LIMIT:]:
            self._insert(record)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def append_log(self, record: tuple[str, Msg]) -> None:
        self.log_box.configure(state="normal")
        self._insert(record)
        # Mantém só as últimas linhas (o log pode crescer por dias)
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > LOG_LIMIT:
            self.log_box.delete("1.0", f"{lines - LOG_LIMIT + 1}.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _insert(self, record: tuple[str, Msg]) -> None:
        timestamp, msg = record
        self.log_box.insert("end", f"[{timestamp}]  ", "time")
        level = _level(msg)
        self.log_box.insert("end", msg.render() + "\n", level if level else ())
