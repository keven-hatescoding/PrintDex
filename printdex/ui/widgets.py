"""Widgets reutilizáveis da interface."""

import tkinter
from collections.abc import Callable

import customtkinter as ctk

from printdex.ui import theme


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


class Card(ctk.CTkFrame):
    """Card clicável da Biblioteca: ícone, nome e detalhe."""

    def __init__(self, master, image: ctk.CTkImage | None, icon_text: str,
                 title: str, detail: str, command: Callable[[], None]) -> None:
        super().__init__(master, cursor="hand2", **theme.CARD)
        self._command = command
        self._hover_job: str | None = None
        self.grid_columnconfigure(0, weight=1)

        icon = ctk.CTkLabel(self, text="" if image else icon_text, image=image,
                            font=ctk.CTkFont(family="Segoe UI Emoji", size=40),
                            cursor="hand2")
        icon.grid(row=0, column=0, pady=(18, 8))
        name = WrapLabel(self, text=title, font=theme.font(14, "bold"),
                         text_color=theme.TEXT, justify="center", anchor="center",
                         wraplength=140, cursor="hand2")
        name.grid(row=1, column=0, sticky="ew", padx=12)
        info = ctk.CTkLabel(self, text=detail, font=theme.font(12),
                            text_color=theme.TEXT_MUTED, cursor="hand2")
        info.grid(row=2, column=0, pady=(2, 16))

        for widget in (self, icon, name, info):
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
            widget.bind("<Button-1>", self._on_click, add="+")

    def _on_enter(self, _event=None) -> None:
        self.configure(fg_color=theme.CARD_HOVER, border_color=theme.ACCENT)

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
        self.configure(fg_color=theme.CARD_BG, border_color=theme.CARD_BORDER)

    def _on_click(self, _event=None) -> None:
        # Pela janela: a ação pode destruir este card (ex.: navegar)
        self.winfo_toplevel().after_idle(self._command)

    def destroy(self) -> None:
        if self._hover_job is not None:
            self.after_cancel(self._hover_job)
        super().destroy()


def ghost_button(master, text: str, command: Callable[[], None], **kwargs) -> ctk.CTkButton:
    """Botão secundário: fundo transparente com borda fina."""
    options = dict(height=32, corner_radius=8, border_width=1,
                   fg_color="transparent", border_color=theme.CARD_BORDER,
                   hover_color=theme.NAV_HOVER, text_color=theme.TEXT,
                   text_color_disabled=theme.TEXT_DISABLED, font=theme.font(13))
    options.update(kwargs)
    return ctk.CTkButton(master, text=text, command=command, **options)
