"""Widgets reutilizáveis da interface."""

import queue
import threading
import time
import tkinter
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageSequence

from sliceminddex.ui import theme


def fit_size(size: tuple[int, int], box: tuple[int, int]) -> tuple[int, int]:
    """Tamanho que cabe em `box` mantendo a proporção."""
    scale = min(box[0] / size[0], box[1] / size[1])
    return max(1, round(size[0] * scale)), max(1, round(size[1] * scale))


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


class Tooltip:
    """Balão de dica ao lado de um widget do CustomTkinter, com o mouse em cima.

    Um widget do CustomTkinter é feito de várias partes (canvas, texto):
    passar de uma para outra gera <Leave> e <Enter> seguidos. Por isso a
    saída é conferida pela posição do mouse, sem o balão piscar.
    """

    DELAY_MS = 150

    def __init__(self, widget: ctk.CTkBaseClass, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip: tkinter.Toplevel | None = None
        self._job: str | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", lambda _e: self.hide(), add="+")

    def _on_enter(self, _event=None) -> None:
        if self._tip is None and self._job is None:
            self._job = self.widget.after(self.DELAY_MS, self.show)

    def _on_leave(self, _event=None) -> None:
        self.widget.after(40, self._check_pointer)

    def _check_pointer(self) -> None:
        try:
            widget = self.widget.winfo_containing(*self.widget.winfo_pointerxy())
        except (KeyError, tkinter.TclError):  # ponteiro sobre um menu, janela fechada
            widget = None
        while widget is not None:
            if widget is self.widget:
                return  # ainda em cima (passou de uma parte do botão para outra)
            widget = widget.master
        self.hide()

    def show(self) -> None:
        self._job = None
        if self._tip is not None or not self.widget.winfo_ismapped():
            return
        widget = self.widget
        tip = tkinter.Toplevel(widget)
        tip.overrideredirect(True)  # sem barra de título nem borda
        tip.attributes("-topmost", True)
        tkinter.Label(tip, text=self.text, justify="left", padx=10, pady=6, bd=0,
                      bg=widget._apply_appearance_mode(theme.TOOLTIP_BG),
                      fg=widget._apply_appearance_mode(theme.TOOLTIP_TEXT),
                      font=widget._apply_font_scaling(theme.font(12, "bold"))).pack()
        tip.update_idletasks()
        # À direita do widget, centralizado na altura; sem espaço, à esquerda
        gap = round(8 * widget._get_widget_scaling())
        x = widget.winfo_rootx() + widget.winfo_width() + gap
        if x + tip.winfo_reqwidth() > widget.winfo_screenwidth():
            x = widget.winfo_rootx() - gap - tip.winfo_reqwidth()
        y = widget.winfo_rooty() + (widget.winfo_height() - tip.winfo_reqheight()) // 2
        tip.geometry(f"+{max(0, x)}+{max(0, y)}")
        self._tip = tip

    def hide(self) -> None:
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


_STATIC = object()  # a imagem tem um quadro só: nada mais a tocar
_FAILED = object()  # arquivo ilegível


class GifPlayer(ctk.CTkLabel):
    """Toca um GIF animado em loop, sem travar a interface.

    Uma thread lê e reduz os quadros (o Pillow solta o GIL ao decodificar e
    redimensionar) e os passa por uma fila curta; a thread da interface só
    troca a imagem na hora de cada quadro, com after(). A memória fica
    constante mesmo num GIF longo: só alguns quadros prontos por vez, em vez
    do GIF inteiro descompactado (uma gravação de tela passaria de 200 MB).

    Sem o arquivo, ou com um arquivo ilegível, mostra `missing_text`.
    """

    BUFFER = 4  # quadros prontos à frente

    def __init__(self, master, path: Path, max_size: tuple[int, int],
                 missing_text: str = "", **kwargs) -> None:
        super().__init__(master, text="", **kwargs)
        self._missing_text = missing_text
        self._frames: queue.Queue = queue.Queue(maxsize=self.BUFFER)
        self._stop = threading.Event()
        self._job: str | None = None
        self._due: float | None = None  # hora em que o próximo quadro deve aparecer
        self.size: tuple[int, int] | None = None  # tamanho exibido, sem a escala de DPI
        try:
            with Image.open(path) as gif:  # só o cabeçalho: rápido
                self.size = fit_size(gif.size, max_size)
        except (OSError, ValueError):
            self._show_missing()
            return
        scaling = self._get_widget_scaling()
        pixels = (round(self.size[0] * scaling), round(self.size[1] * scaling))
        self.configure(width=self.size[0], height=self.size[1])  # reserva o espaço já
        threading.Thread(target=self._decode, args=(Path(path), pixels),
                         name="SliceMindDex-Gif", daemon=True).start()
        self._job = self.after(10, self._tick)

    # -------------------------------------------------- thread de leitura

    def _decode(self, path: Path, pixels: tuple[int, int]) -> None:
        try:
            with Image.open(path) as gif:
                while not self._stop.is_set():
                    count = 0
                    for frame in ImageSequence.Iterator(gif):
                        duration = frame.info.get("duration") or 0
                        image = frame.convert("RGBA").resize(pixels, Image.Resampling.LANCZOS)
                        # Como os navegadores: tempos de até 10 ms valem 100 ms
                        if not self._put((image, duration if duration > 10 else 100)):
                            return
                        count += 1
                    if count <= 1:
                        self._put(_STATIC)
                        return
        except Exception:  # GIF corrompido: mostra o texto no lugar
            self._put(_FAILED)

    def _put(self, item) -> bool:
        """Entrega à interface; False se o player foi fechado."""
        while not self._stop.is_set():
            try:
                self._frames.put(item, timeout=0.2)
                return True
            except queue.Full:
                continue
        return False

    # ---------------------------------------------------- thread da tela

    def _tick(self) -> None:
        self._job = None
        try:
            item = self._frames.get_nowait()
        except queue.Empty:
            self._job = self.after(10, self._tick)  # a leitura está um pouco atrás
            return
        if item is _STATIC:
            return
        if item is _FAILED:
            self._show_missing()
            return
        image, duration = item
        self.configure(image=ctk.CTkImage(image, image, size=self.size))
        # Cada quadro tem hora marcada (a anterior + a duração): o tempo de
        # trocar a imagem não se acumula e o GIF anda no ritmo do arquivo.
        # Muito atrasado (ex.: janela arrastada), recomeça a contar de agora.
        now = time.perf_counter()
        if self._due is None or now - self._due > 0.5:
            self._due = now
        self._due += duration / 1000
        self._job = self.after(max(1, round((self._due - now) * 1000)), self._tick)

    def _show_missing(self) -> None:
        self.configure(image=None, text=self._missing_text, width=0, height=0)

    def destroy(self) -> None:
        self._stop.set()  # a thread de leitura termina em até 0,2 s
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        super().destroy()
