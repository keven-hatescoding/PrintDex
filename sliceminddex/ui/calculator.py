"""Tela Calculadora: custo e preço de uma impressão 3D, em tempo real.

Os dois modos (Simples e Avançado) usam as MESMAS variáveis (app.calc_vars):
o que se digita num aparece preenchido no outro. Qualquer mudança recalcula
na hora (trace_add), sem botão "calcular". A moeda vem das Configurações e
muda rótulos e valores imediatamente (apply_currency).
"""

import customtkinter as ctk

from sliceminddex.core import calculator as calc
from sliceminddex.locales import t, tn
from sliceminddex.ui import theme
from sliceminddex.ui.widgets import Section, ViewHeader

# (ícone, título, campos) de cada bloco
SIMPLE_BLOCKS = (
    ("🧵", "calc.sec.filament", ("price_kg",)),
    ("✂", "calc.sec.slicer", ("weight", "hours")),
    ("⚡", "calc.sec.energy", ("tariff", "power")),
    ("💰", "calc.sec.profit", ("margin",)),
)
ADVANCED_SECTIONS = (
    ("🧵", "calc.sec.material", ("weight", "price_kg", "hours", "power")),
    ("⚙", "calc.sec.operation", ("tariff", "machine", "lifetime", "labor_rate",
                                 "labor_hours", "quantity")),
    ("📈", "calc.sec.extras", ("margin", "risk")),
)
SIMPLE_PARTS = (("material", "calc.r.material"), ("energy", "calc.r.energy"),
                ("total", "calc.r.total_cost"), ("profit", "calc.r.profit"))
DASH_CARDS = (("unit_cost", "calc.r.unit_cost"), ("unit_profit", "calc.r.unit_profit"),
              ("total_time", "calc.r.total_time"), ("filament_only", "calc.r.filament_only"))
# Anatomia do custo: parte, rótulo, cor da barra
ANATOMY = (
    ("material", "calc.r.filament", "#3B82F6"),
    ("energy", "calc.r.energy", "#F59E0B"),
    ("machine", "calc.r.machine", "#8B5CF6"),
    ("labor", "calc.r.labor", "#14B8A6"),
    ("failure", "calc.r.failures", "#EF4444"),
)

# Painel de resultados do modo avançado: escuro nos dois temas
DASH_BG = ("#1B1F24", "#0F1215")
DASH_CARD = ("#272C33", "#1A1E23")
DASH_TEXT = "#F1F3F5"
DASH_MUTED = "#9AA3AD"
DASH_TRACK = "#323840"
PRICE_COLOR = ("#00A846", "#34D27B")

SIMPLE_MAX_WIDTH = 920   # o modo simples fica centralizado até esta largura
SIMPLE_TWO_COLUMNS = 620  # blocos 2x2 a partir desta largura (sem DPI)
ADVANCED_SPLIT = 860     # avançado em duas colunas a partir desta largura


class CalculatorView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._entries: dict[str, list[ctk.CTkEntry]] = {}
        self._unit_labels: list[tuple[ctk.CTkLabel, str]] = []  # rótulos com moeda
        self._traces: list[tuple[ctk.StringVar, str]] = []
        self._jobs: dict[str, str] = {}
        self._simple_columns = 0
        self._split: bool | None = None
        self._entry_border = ctk.ThemeManager.theme["CTkEntry"]["border_color"]

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ViewHeader(self, t("calc.title"), t("calc.subtitle")).grid(
            row=0, column=0, sticky="ew", pady=(0, 14))

        self._modes = {t("calc.mode.simple"): "simple", t("calc.mode.advanced"): "advanced"}
        self.mode_buttons = ctk.CTkSegmentedButton(
            self, values=list(self._modes), command=self._on_mode,
            height=36, font=theme.font(13, "bold"))
        self.mode_buttons.grid(row=1, column=0, sticky="w", pady=(0, 14))

        self.simple = self._build_simple()
        self.advanced = self._build_advanced()
        for frame in (self.simple, self.advanced):
            frame.grid(row=2, column=0, sticky="nsew")
            frame.grid_remove()
        self._show_mode(app.calc_mode)

        for var in app.calc_vars.values():
            trace = var.trace_add("write", lambda *_: self._debounce("calc", 30, self.recalculate))
            self._traces.append((var, trace))
        self.recalculate()

    # ------------------------------------------------------------- campos

    def _field(self, section: Section, name: str) -> None:
        key = f"calc.f.{name}"
        row = section.field(t(key, cur=calc.currency_symbol(self.app.currency)))
        self._unit_labels.append((row.label, key))
        entry = ctk.CTkEntry(row, textvariable=self.app.calc_vars[name], height=36,
                             font=theme.font(14))
        entry.grid(row=0, column=0, sticky="ew")
        self._entries.setdefault(name, []).append(entry)

    # -------------------------------------------------------- modo simples

    def _build_simple(self) -> ctk.CTkScrollableFrame:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll.grid_columnconfigure(0, weight=1)
        self._simple_inner = inner = ctk.CTkFrame(scroll, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew")

        self._blocks = []
        for icon, key, fields in SIMPLE_BLOCKS:
            section = Section(inner, f"{icon}  {t(key)}")
            for name in fields:
                self._field(section, name)
            self._blocks.append(section)

        # Resultado: o preço sugerido em destaque, logo abaixo dos campos
        card = self._simple_result = ctk.CTkFrame(
            inner, corner_radius=18, border_width=2,
            fg_color=theme.CARD_BG, border_color=theme.ACCENT)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=t("calc.r.suggested"), font=theme.font(13, "bold"),
                     text_color=theme.TEXT_MUTED).grid(row=0, column=0, pady=(20, 0))
        self.simple_price = ctk.CTkLabel(card, text="", font=theme.font(52, "bold"),
                                         text_color=PRICE_COLOR)
        self.simple_price.grid(row=1, column=0, padx=16)
        self._simple_parts_frame = parts = ctk.CTkFrame(card, fg_color="transparent")
        parts.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 20))
        self.simple_parts: dict[str, ctk.CTkLabel] = {}
        self._simple_cells = []
        for name, key in SIMPLE_PARTS:
            cell = ctk.CTkFrame(parts, fg_color="transparent")
            ctk.CTkLabel(cell, text=t(key), font=theme.font(12),
                         text_color=theme.TEXT_MUTED).pack()
            value = ctk.CTkLabel(cell, text="", font=theme.font(16, "bold"),
                                 text_color=theme.TEXT)
            value.pack()
            self.simple_parts[name] = value
            self._simple_cells.append(cell)

        scroll.bind("<Configure>", lambda _e: self._debounce("simple", 60, self._layout_simple), "+")
        return scroll

    def _layout_simple(self) -> None:
        width = self.simple.winfo_width() / self.simple._get_widget_scaling()
        if width <= 1:
            return
        # Centralizado, com largura máxima: não se espalha em telas grandes
        side = max(0, int((width - SIMPLE_MAX_WIDTH) / 2))
        self._simple_inner.grid(padx=side)
        columns = 2 if width - 2 * side >= SIMPLE_TWO_COLUMNS else 1
        if columns != self._simple_columns:
            self._simple_columns = columns
            inner = self._simple_inner
            for index in range(2):
                inner.grid_columnconfigure(index, weight=1 if index < columns else 0,
                                           uniform="blocks" if index < columns else "")
            for index, block in enumerate(self._blocks):
                row, column = divmod(index, columns)
                block.grid(row=row, column=column, sticky="nsew", pady=(0, 14),
                           padx=(0, 7) if columns == 2 and column == 0 else
                           (7, 0) if columns == 2 else 0)
            self._simple_result.grid(row=len(self._blocks), column=0, columnspan=columns,
                                     sticky="ew", pady=(4, 8))
            # Detalhes do resultado: 4 lado a lado, ou 2x2 em telas estreitas
            per_row = 4 if columns == 2 else 2
            for index in range(4):
                self._simple_parts_frame.grid_columnconfigure(
                    index, weight=1 if index < per_row else 0,
                    uniform="parts" if index < per_row else "")
            for index, cell in enumerate(self._simple_cells):
                cell.grid(row=index // per_row, column=index % per_row, pady=4)
        self._fit(self.simple_price, width - 2 * side - 40, 52)

    # ------------------------------------------------------- modo avançado

    def _build_advanced(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color="transparent")

        self._form = form = ctk.CTkScrollableFrame(frame, fg_color="transparent", corner_radius=0)
        form.grid_columnconfigure(0, weight=1)
        for row, (icon, key, fields) in enumerate(ADVANCED_SECTIONS):
            section = Section(form, f"{icon}  {t(key)}")
            for name in fields:
                self._field(section, name)
            section.grid(row=row, column=0, sticky="ew", pady=(0, 14), padx=(0, 4))

        # Painel de resultados (escuro, com rolagem se a janela for baixa)
        self._dash = dash = ctk.CTkScrollableFrame(frame, fg_color=DASH_BG, corner_radius=18)
        dash.grid_columnconfigure((0, 1), weight=1, uniform="dash")
        ctk.CTkLabel(dash, text=t("calc.r.suggested"), font=theme.font(13, "bold"),
                     text_color=DASH_MUTED, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 0))
        self.adv_price = ctk.CTkLabel(dash, text="", font=theme.font(46, "bold"),
                                      text_color=PRICE_COLOR, anchor="w")
        self.adv_price.grid(row=1, column=0, columnspan=2, sticky="w", padx=18)
        self.adv_quantity = ctk.CTkLabel(dash, text="", font=theme.font(13),
                                         text_color=DASH_MUTED, anchor="w")
        self.adv_quantity.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 14))

        self.dash_cards: dict[str, ctk.CTkLabel] = {}
        for index, (name, key) in enumerate(DASH_CARDS):
            card = ctk.CTkFrame(dash, fg_color=DASH_CARD, corner_radius=12)
            row, column = divmod(index, 2)
            card.grid(row=3 + row, column=column, sticky="nsew", pady=5,
                      padx=(20, 5) if column == 0 else (5, 20))
            ctk.CTkLabel(card, text=t(key), font=theme.font(12), text_color=DASH_MUTED,
                         anchor="w").pack(fill="x", padx=14, pady=(10, 0))
            value = ctk.CTkLabel(card, text="", font=theme.font(17, "bold"),
                                 text_color=DASH_TEXT, anchor="w")
            value.pack(fill="x", padx=14, pady=(0, 10))
            self.dash_cards[name] = value

        ctk.CTkLabel(dash, text=t("calc.r.anatomy"), font=theme.font(14, "bold"),
                     text_color=DASH_TEXT, anchor="w").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=20, pady=(22, 6))
        self.anatomy: dict[str, tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = {}
        for index, (name, key, color) in enumerate(ANATOMY):
            line = ctk.CTkFrame(dash, fg_color="transparent")
            line.grid(row=6 + index, column=0, columnspan=2, sticky="ew", padx=20, pady=(6, 0))
            line.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(line, text=f"●  {t(key)}", font=theme.font(12, "bold"),
                         text_color=color, anchor="w").grid(row=0, column=0, sticky="w")
            value = ctk.CTkLabel(line, text="", font=theme.font(12), text_color=DASH_TEXT,
                                 anchor="e")
            value.grid(row=0, column=1, sticky="e")
            bar = ctk.CTkProgressBar(line, height=6, corner_radius=3,
                                     fg_color=DASH_TRACK, progress_color=color)
            bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
            self.anatomy[name] = (value, bar)
        ctk.CTkFrame(dash, height=18, fg_color="transparent").grid(row=20, column=0)

        frame.bind("<Configure>", lambda _e: self._debounce("advanced", 60, self._layout_advanced))
        return frame

    def _layout_advanced(self) -> None:
        width = self.advanced.winfo_width() / self.advanced._get_widget_scaling()
        if width <= 1:
            return
        split = width >= ADVANCED_SPLIT
        if split != self._split:
            self._split = split
            frame = self.advanced
            if split:  # formulário à esquerda, painel à direita
                frame.grid_columnconfigure(0, weight=3, uniform="advanced")
                frame.grid_columnconfigure(1, weight=2, uniform="advanced")
                frame.grid_rowconfigure(0, weight=1)
                frame.grid_rowconfigure(1, weight=0)
                self._form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
                self._dash.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
            else:      # janela estreita: painel em cima, formulário embaixo
                frame.grid_columnconfigure(0, weight=1, uniform="")
                frame.grid_columnconfigure(1, weight=0, uniform="")
                frame.grid_rowconfigure(0, weight=2)
                frame.grid_rowconfigure(1, weight=3)
                self._dash.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 12))
                self._form.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        dash_width = width * 2 / 5 if split else width
        self._fit(self.adv_price, dash_width - 60, 46)

    # ------------------------------------------------------------ cálculo

    def recalculate(self) -> None:
        values = {}
        for name, var in self.app.calc_vars.items():
            value = calc.parse_number(var.get())
            # Valor inválido: borda vermelha e conta como 0
            for entry in self._entries.get(name, []):
                entry.configure(border_color=theme.DANGER if value is None else self._entry_border)
            values[name] = value or 0.0
        if not self.app.calc_vars["quantity"].get().strip():
            values["quantity"] = 1.0  # quantidade em branco = 1 peça

        def money(amount: float) -> str:
            return calc.format_money(amount, self.app.currency)

        simple = calc.simple(values["price_kg"], values["weight"], values["hours"],
                             values["tariff"], values["power"], values["margin"])
        self.simple_price.configure(text=money(simple.price))
        for name, label in self.simple_parts.items():
            label.configure(text=money(getattr(simple, name)))

        result = calc.advanced(
            weight_g=values["weight"], price_kg=values["price_kg"], hours=values["hours"],
            power_w=values["power"], tariff=values["tariff"], machine_price=values["machine"],
            lifetime_h=values["lifetime"], labor_rate=values["labor_rate"],
            labor_hours=values["labor_hours"], quantity=values["quantity"],
            margin=values["margin"], risk=values["risk"])
        self.adv_price.configure(text=money(result.final_price))
        quantity = result.quantity
        self.adv_quantity.configure(
            text=tn("calc.r.for_qty", int(quantity) if quantity.is_integer() else quantity))
        hours = int(result.total_hours)
        minutes = round((result.total_hours - hours) * 60)
        if minutes == 60:
            hours, minutes = hours + 1, 0
        self.dash_cards["unit_cost"].configure(text=money(result.unit_cost))
        self.dash_cards["unit_profit"].configure(text=money(result.unit_profit))
        self.dash_cards["total_time"].configure(text=t("calc.duration", h=hours, m=minutes))
        self.dash_cards["filament_only"].configure(text=money(result.material))
        shares = result.shares()
        for name, (label, bar) in self.anatomy.items():
            amount = getattr(result, name)
            label.configure(text=f"{money(amount)}  ·  {shares[name] * 100:.0f}%")
            bar.set(shares[name])

        self._fit(self.simple_price, self._simple_available(), 52)

    def apply_currency(self) -> None:
        """A moeda mudou nas Configurações: rótulos e valores na hora."""
        symbol = calc.currency_symbol(self.app.currency)
        for label, key in self._unit_labels:
            label.configure(text=t(key, cur=symbol))
        self.recalculate()

    # ------------------------------------------------------------- layout

    def _on_mode(self, display_name: str) -> None:
        self.app.calc_mode = self._modes[display_name]
        self._show_mode(self.app.calc_mode)

    def _show_mode(self, mode: str) -> None:
        names = {code: name for name, code in self._modes.items()}
        self.mode_buttons.set(names[mode])
        shown, hidden = ((self.simple, self.advanced) if mode == "simple"
                         else (self.advanced, self.simple))
        hidden.grid_remove()
        shown.grid()

    def _simple_available(self) -> float:
        width = self._simple_inner.winfo_width() / self.simple._get_widget_scaling()
        return width - 40 if width > 1 else 600

    def _fit(self, label: ctk.CTkLabel, available: float, max_size: int) -> None:
        """Diminui a fonte do preço grande para ele caber (ex.: R$ 1.234.567,89)."""
        length = max(len(label.cget("text")), 1)
        size = int(min(max_size, max(22, available / (length * 0.62))))
        label.configure(font=theme.font(size, "bold"))

    # ------------------------------------------------------------ after()

    def _debounce(self, name: str, delay_ms: int, func) -> None:
        job = self._jobs.pop(name, None)
        if job is not None:
            self.after_cancel(job)

        def run() -> None:
            self._jobs.pop(name, None)
            func()

        self._jobs[name] = self.after(delay_ms, run)

    def destroy(self) -> None:
        # As variáveis são do app e sobrevivem à tela: tira os traces daqui
        for var, trace in self._traces:
            var.trace_remove("write", trace)
        for job in self._jobs.values():
            self.after_cancel(job)
        self._jobs.clear()
        super().destroy()
