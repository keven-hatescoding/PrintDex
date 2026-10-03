"""Widgets reutilizáveis da interface."""

import tkinter
from collections.abc import Callable

import customtkinter as ctk

from sliceminddex.ui import theme


class WrapLabel(ctk.CTkLabel):
    """Label que quebra o texto na largura que o layout lhe dá.

    Um label comum pede a largura do texto inteiro: um caminho longo
    alargaria a coluna e empurraria o resto da tela para fora da janela.
    """

    def __init__(self, master, justify: str = "left", anchor: str = "w", **kwargs) -> None:
        kwargs.setdefault("wraplength", 300)
        super().__init__(master, justify=justify, anchor=anchor, **kwargs)
        self._wrap_width = 0
        # No frame externo (a área que o grid deu ao label), não no texto
        tkinter.Frame.bind(self, "<Configure>", self._rewrap, "+")

    def _rewrap(self, event: tkinter.Event) -> None:
        width = int(event.width / self._get_widget_scaling()) - 6
        if width > 20 and width != self._wrap_width:
            self._wrap_width = width
            self.configure(wraplength=width)


class ViewHeader(ctk.CTkFrame):
    """Título e subtítulo de uma tela."""

    def __init__(self, master, title: str, subtitle: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=theme.font(26, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=0, sticky="w")
        WrapLabel(self, text=subtitle, font=theme.font(13),
                  text_color=theme.TEXT_MUTED).grid(row=1, column=0, sticky="ew", pady=(2, 0))


class Section(ctk.CTkFrame):
    """Card com título; `field()` acrescenta rótulo, dica e linha de controles.

    Os campos ficam empilhados (rótulo em cima, controles embaixo), o que
    funciona em qualquer largura de janela.
    """

    def __init__(self, master, title: str) -> None:
        super().__init__(master, **theme.CARD)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=theme.font(16, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(
            row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        self._row = 1
        # Respiro no fim do card
        ctk.CTkFrame(self, height=10, fg_color="transparent").grid(row=999, column=0)

    def field(self, label: str, hint: str | None = None) -> ctk.CTkFrame:
        """Linha de controles do campo; o rótulo fica em `row.label`."""
        title = ctk.CTkLabel(self, text=label, font=theme.font(13, "bold"),
                             text_color=theme.TEXT, anchor="w")
        title.grid(row=self._row, column=0, sticky="w", padx=20, pady=(12, 0))
        self._row += 1
        if hint:
            WrapLabel(self, text=hint, font=theme.font(12),
                      text_color=theme.TEXT_MUTED).grid(
                row=self._row, column=0, sticky="ew", padx=20)
            self._row += 1
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=self._row, column=0, sticky="ew", padx=20, pady=(6, 0))
        row.grid_columnconfigure(0, weight=1)
        row.label = title
        self._row += 1
        return row

    def add(self, widget: tkinter.Misc, **grid) -> None:
        """Acrescenta um widget próprio (ex.: um aviso) como nova linha."""
        widget.grid(row=self._row, column=0, sticky="ew", padx=20, **grid)
        self._row += 1


def _longest(limit: int, fits: Callable[[int], bool]) -> int:
    """Maior n em [0, limit] com fits(n) verdadeiro (busca binária: fits vale
    para todo n até a resposta e falha depois dela)."""
    low, high = 0, limit
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    return low


def elide(text: str, measure: Callable[[str], int], width: int,
          max_lines: int = 2, keep_end: int = 8) -> str:
    """Quebra o texto em até max_lines linhas de no máximo `width` px.

    Quebra de preferência depois de espaço, "_" ou "-". Se não couber,
    a última linha perde o meio e mantém os últimos `keep_end` caracteres.
    """
    lines: list[str] = []
    rest = text
    while rest:
        if measure(rest) <= width:
            lines.append(rest)
            break
        if len(lines) == max_lines - 1:
            tail = rest[-keep_end:] if measure("…" + rest[-keep_end:]) <= width else ""
            head = rest[:len(rest) - len(tail)]
            size = _longest(len(head), lambda n: measure(head[:n].rstrip() + "…" + tail) <= width)
            lines.append(head[:size].rstrip() + "…" + tail)
            break
        cut = max(1, _longest(len(rest), lambda n: measure(rest[:n]) <= width))
        breaks = [rest.rfind(separator, 0, cut) for separator in " _-"]
        if max(breaks) >= cut // 2:  # só se não desperdiçar meia linha
            cut = max(breaks) + 1
        lines.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    return "\n".join(lines)


class _CardText(tkinter.Label):
    """Texto de um card da Biblioteca: um tkinter.Label simples.

    Um CTkLabel custa cerca de 3x mais para criar e desenhar (é um frame com
    um canvas que imita o fundo) e uma pasta pode ter centenas de cards. O
    card repassa as cores (tema, hover) e a escala de DPI por restyle().

    Com max_lines, ocupa só a largura que o layout lhe dá (como o WrapLabel)
    e corta o texto com reticências: nomes longos perdem o meio e mantêm o
    fim ("goku_ultra_inst…(2).3mf"), que costuma diferenciar arquivos parecidos.
    """

    def __init__(self, card: ctk.CTkFrame, text: str, font: ctk.CTkFont,
                 color: tuple[str, str], max_lines: int | None = None) -> None:
        # Com corte, começa vazio: o texto inteiro pediria a largura dele e
        # alargaria a coluna
        super().__init__(card, text="" if max_lines else text, bd=0, padx=0, pady=0,
                         highlightthickness=0, justify="center", cursor="hand2")
        self._card = card
        self._full_text = text
        self._ctk_font = font
        self._color = color
        self._max_lines = max_lines
        self._fitted_width = 0
        self.restyle()
        if max_lines:
            self.bind("<Configure>", self._refit, add="+")

    def restyle(self) -> None:
        """Cores do tema e do fundo atual do card; fonte na escala atual."""
        card = self._card
        self.configure(bg=card._apply_appearance_mode(card.cget("fg_color")),
                       fg=card._apply_appearance_mode(self._color),
                       font=card._apply_font_scaling(self._ctk_font))

    def _refit(self, event: tkinter.Event) -> None:
        width = int(event.width / self._card._get_widget_scaling()) - 4
        if width > 20 and width != self._fitted_width:
            self._fitted_width = width
            # CTkFont mede sem a escala de DPI, na mesma unidade de `width`
            self.configure(text=elide(self._full_text, self._ctk_font.measure, width,
                                      self._max_lines))


class _ClickableCard(ctk.CTkFrame):
    """Card da Biblioteca que reage ao mouse como um botão."""

    def __init__(self, master, command: Callable[[], None]) -> None:
        super().__init__(master, cursor="hand2", **theme.CARD)
        self._command = command
        self._hover_job: str | None = None
        self._texts: list[_CardText] = []

    def _text(self, text: str, font: ctk.CTkFont, color: tuple[str, str],
              max_lines: int | None = None) -> _CardText:
        label = _CardText(self, text, font, color, max_lines)
        self._texts.append(label)
        return label

    def _bind_children(self, *widgets: tkinter.Misc) -> None:
        # O bind de um CTkFrame só pega o fundo: os filhos também precisam
        for widget in (self, *widgets):
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
            widget.bind("<Button-1>", self._on_click, add="+")
        # Mãozinha em todo o card: os widgets do CustomTkinter desenham num
        # canvas interno que não herda o cursor do frame (margem, bordas).
        # O winfo_children do tkinter: o do CTkFrame esconde esse canvas.
        pending = [self]
        while pending:
            widget = pending.pop()
            tkinter.Misc.configure(widget, cursor="hand2")
            pending.extend(tkinter.Misc.winfo_children(widget))

    def _set_colors(self, fg_color, border_color) -> None:
        self.configure(fg_color=fg_color, border_color=border_color)
        for label in self._texts:
            label.restyle()

    # O CustomTkinter avisa os widgets dele ao trocar o tema e a escala de
    # DPI; os textos simples acompanham por aqui
    def _set_appearance_mode(self, mode_string) -> None:
        super()._set_appearance_mode(mode_string)
        for label in self._texts:
            label.restyle()

    def _set_scaling(self, *args, **kwargs) -> None:
        super()._set_scaling(*args, **kwargs)
        for label in self._texts:
            label.restyle()

    def _on_enter(self, _event=None) -> None:
        self._set_colors(theme.CARD_HOVER, theme.ACCENT)

    def _on_leave(self, _event=None) -> None:
        # Passar do card para um filho também dispara <Leave>: confere depois
        if self._hover_job is None:
            self._hover_job = self.after(30, self._check_hover)

    def _check_hover(self) -> None:
        self._hover_job = None
        widget = self.winfo_containing(*self.winfo_pointerxy())
        while widget is not None:
            if widget is self:
                return
            widget = widget.master
        self._set_colors(theme.CARD_BG, theme.CARD_BORDER)

    def _on_click(self, _event=None) -> None:
        # Pela janela: a ação pode destruir este card (ex.: navegar)
        self.winfo_toplevel().after_idle(self._command)

    def destroy(self) -> None:
        if self._hover_job is not None:
            self.after_cancel(self._hover_job)
        super().destroy()


class Card(_ClickableCard):
    """Card de pasta da Biblioteca: ícone, nome e detalhe."""

    def __init__(self, master, image: ctk.CTkImage | None, icon_text: str,
                 title: str, detail: str, command: Callable[[], None]) -> None:
        super().__init__(master, command)
        self.grid_columnconfigure(0, weight=1)

        icon = ctk.CTkLabel(self, text="" if image else icon_text, image=image,
                            font=ctk.CTkFont(family="Segoe UI Emoji", size=40),
                            cursor="hand2")
        icon.grid(row=0, column=0, pady=(18, 8))
        name = self._text(title, theme.font(14, "bold"), theme.TEXT, max_lines=3)
        name.grid(row=1, column=0, sticky="ew", padx=12)
        info = self._text(detail, theme.font(12), theme.TEXT_MUTED)
        info.grid(row=2, column=0, pady=(2, 16))
        self._bind_children(icon, name, info)


class ThumbnailCard(_ClickableCard):
    """Card de arquivo da Biblioteca: miniatura, nome (até 2 linhas) e tamanho.

    A miniatura chega depois, por set_image(), carregada em segundo plano;
    até lá aparece só o fundo do quadro.
    """

    def __init__(self, master, title: str, detail: str, command: Callable[[], None],
                 tile_height: int) -> None:
        super().__init__(master, command)
        self.grid_columnconfigure(0, weight=1)
        # Num card esticado pela linha, a sobra fica sob o nome: os tamanhos
        # dos cards da mesma linha ficam alinhados embaixo
        self.grid_rowconfigure(1, weight=1)

        self.tile = ctk.CTkLabel(self, text="", height=tile_height, corner_radius=8,
                                 fg_color=theme.THUMB_BG, cursor="hand2")
        self.tile.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))
        name = self._text(title, theme.font(13, "bold"), theme.TEXT, max_lines=2)
        name.grid(row=1, column=0, sticky="new", padx=10)
        info = self._text(detail, theme.font(12), theme.TEXT_MUTED)
        info.grid(row=2, column=0, pady=(2, 10))
        self._bind_children(self.tile, name, info)

    def set_image(self, image: ctk.CTkImage) -> None:
        self.tile.configure(image=image)


def ghost_button(master, text: str, command: Callable[[], None], **kwargs) -> ctk.CTkButton:
    """Botão secundário: fundo transparente com borda fina."""
    options = dict(height=32, corner_radius=8, border_width=1,
                   fg_color="transparent", border_color=theme.CARD_BORDER,
                   hover_color=theme.NAV_HOVER, text_color=theme.TEXT,
                   text_color_disabled=theme.TEXT_DISABLED, font=theme.font(13))
    options.update(kwargs)
    return ctk.CTkButton(master, text=text, command=command, **options)
