"""Cores e fontes da interface.

Cada cor é um par (modo claro, modo escuro): o CustomTkinter troca sozinho
quando o tema muda, inclusive no modo "System".
"""

import customtkinter as ctk

from printdex import locales

# Destaque verde, comum em softwares de impressão 3D
ACCENT = ("#00A846", "#00AE42")
ACCENT_HOVER = ("#008F3B", "#00953A")
DANGER = ("#D93F3F", "#D64545")
DANGER_HOVER = ("#B83232", "#B53A3A")
BUTTON_DISABLED = ("#D6DADF", "#31363D")
TEXT_DISABLED = ("#8C939B", "#6E757D")
ON_ACCENT = "#FFFFFF"

WINDOW_BG = ("#F2F4F6", "#16181B")
SIDEBAR_BG = ("#FFFFFF", "#1E2125")
CARD_BG = ("#FFFFFF", "#22262B")
CARD_HOVER = ("#F1FAF4", "#2A3037")
CARD_BORDER = ("#E1E4E8", "#2F343B")
TEXT = ("#15171A", "#E8EAED")
TEXT_MUTED = ("#69707A", "#9AA1A9")
NAV_HOVER = ("#EEF1F4", "#2A2E34")
NAV_ACTIVE = ("#E2F5E9", "#1D3828")
NAV_ACTIVE_TEXT = ("#00843A", "#4ADE80")

STATUS_COLORS = {
    "stopped": TEXT_MUTED,
    "running": ("#00A846", "#34D27B"),
    "stopping": ("#D98C00", "#FFB547"),
}

# Cores das linhas do log: tons médios, legíveis no claro e no escuro
LOG_COLORS = {
    "time": "#8B929C",
    "ok": "#22A55A",
    "warn": "#D99A00",
    "error": "#E05252",
}

# Estilo comum dos cards (cartões com borda fina e cantos arredondados)
CARD = {"corner_radius": 14, "border_width": 1,
        "fg_color": CARD_BG, "border_color": CARD_BORDER}


def _family() -> str:
    # Fonte com bom desenho de caracteres chineses; Segoe UI no resto
    return "Microsoft YaHei UI" if locales.get_language() == "zh_CN" else "Segoe UI"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=_family(), size=size, weight=weight)


def mono_font(size: int = 12) -> ctk.CTkFont:
    family = "Microsoft YaHei UI" if locales.get_language() == "zh_CN" else "Consolas"
    return ctk.CTkFont(family=family, size=size)
