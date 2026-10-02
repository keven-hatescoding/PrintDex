"""Tela Biblioteca: navega pela árvore da pasta PRINTS em cards.

PRINTS / categoria / franquia / tipo de item / arquivos. Clicar numa pasta
entra nela; clicar num arquivo abre no programa padrão (ex.: o fatiador).
A grade ajusta o número de colunas à largura da janela.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import customtkinter as ctk

from printdex.locales import t, tn
from printdex.ui import theme
from printdex.ui.icons import FILE_ICON, FOLDER_ICON, category_icon
from printdex.ui.widgets import Card, ViewHeader, WrapLabel, ghost_button

CARD_WIDTH = 172  # largura mínima de um card, antes da escala de DPI
CARD_GAP = 12
BATCH = 24        # cards criados por vez (pastas grandes não travam a tela)
_HIDDEN_NAMES = {"desktop.ini", "thumbs.db"}
_HIDDEN_ATTRIBUTES = 0x2 | 0x4  # FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM


@dataclass(frozen=True)
class _Entry:
    name: str
    path: str
    is_dir: bool
    detail: str


def _visible(entry: os.DirEntry) -> bool:
    name = entry.name
    if name.startswith((".", "~$")) or name.lower() in _HIDDEN_NAMES:
        return False
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return False
    return not attributes & _HIDDEN_ATTRIBUTES


def _size_text(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def _list_folder(folder: Path) -> list[_Entry]:
    """Subpastas (com a contagem de itens) e depois arquivos, em ordem alfabética."""
    folders, files = [], []
    with os.scandir(folder) as entries:
        for entry in entries:
            if not _visible(entry):
                continue
            if entry.is_dir():
                try:
                    with os.scandir(entry.path) as children:
                        count = sum(1 for child in children if _visible(child))
                except OSError:
                    count = 0
                detail = tn("lib.items", count) if count else t("lib.empty_count")
                folders.append(_Entry(entry.name, entry.path, True, detail))
            else:
                try:
                    detail = _size_text(entry.stat().st_size)
                except OSError:
                    detail = ""
                files.append(_Entry(entry.name, entry.path, False, detail))

    def key(item: _Entry) -> str:
        return item.name.casefold()

    return sorted(folders, key=key) + sorted(files, key=key)


class LibraryView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.parts: list[str] = []  # pasta atual, relativa à PRINTS
        self._cards: list[Card] = []
        self._columns = 0
        self._generation = 0  # invalida lotes de uma navegação anterior
        self._jobs: dict[str, str] = {}  # after() pendentes, por nome
        self._restore_scroll: float | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        ViewHeader(self, t("lib.title"), t("lib.subtitle")).grid(
            row=0, column=0, sticky="ew", pady=(0, 18))

        # Botão de destaque: abre a PRINTS no Explorer
        self.local_button = ctk.CTkButton(
            self, text=f"  {t('lib.local_files')}", image=app.icons.get("📂", 38),
            compound="left", height=78, corner_radius=16, font=theme.font(22, "bold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_ACCENT, command=self._open_root,
        )
        self.local_button.grid(row=1, column=0, sticky="ew")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(16, 6))
        toolbar.grid_columnconfigure(1, weight=1)
        self.back_button = ghost_button(toolbar, f"←  {t('lib.back')}", self.go_up)
        self.back_button.grid(row=0, column=0, sticky="w")
        ghost_button(toolbar, f"⟳  {t('lib.refresh')}", self.refresh).grid(
            row=0, column=2, sticky="e", padx=(0, 8))
        self.open_button = ghost_button(toolbar, t("lib.open_here"), self._open_current)
        self.open_button.grid(row=0, column=3, sticky="e")

        self.crumbs = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self.crumbs.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.crumbs.bind("<Configure>", lambda _e: self._debounce("crumbs", 80, self._render_crumbs))

        self.grid_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.grid_frame.grid(row=4, column=0, sticky="nsew")
        self.grid_frame.bind("<Configure>", lambda _e: self._debounce("relayout", 60, self._relayout), "+")

        # Mensagem de pasta vazia / destino ausente (no lugar da grade)
        self.message = ctk.CTkFrame(self, fg_color="transparent")
        self.message.grid_columnconfigure(0, weight=1)
        self.message_icon = ctk.CTkLabel(self.message, text="", image=app.icons.get("🗃", 64))
        self.message_icon.grid(row=0, column=0, pady=(40, 12))
        self.message_text = WrapLabel(self.message, text="", font=theme.font(14),
                                      text_color=theme.TEXT_MUTED, justify="center", anchor="center")
        self.message_text.grid(row=1, column=0, sticky="ew", padx=40)
        self.message_button = ctk.CTkButton(self.message, text=t("lib.go_settings"),
                                            height=36, font=theme.font(13, "bold"),
                                            command=lambda: app.show_view("settings"))

    # ------------------------------------------------------------- navegação

    def root(self) -> Path | None:
        dest = self.app.dest_var.get().strip()
        return Path(dest) if dest else None

    def current(self) -> Path | None:
        root = self.root()
        return root.joinpath(*self.parts) if root else None

    def navigate(self, parts: list[str]) -> None:
        self.parts = list(parts)
        self._restore_scroll = None
        self.refresh()

    def go_up(self) -> None:
        if self.parts:
            self.navigate(self.parts[:-1])

    def refresh(self, keep_scroll: bool = False) -> None:
        root = self.root()
        if root is None or not root.is_dir():
            self.parts = []
            self._show_message(t("lib.no_dest"), with_button=True)
            return
        # Sobe até a pasta existente mais próxima (ex.: pasta apagada no Explorer)
        while self.parts and not root.joinpath(*self.parts).is_dir():
            self.parts.pop()
        try:
            entries = _list_folder(root.joinpath(*self.parts))
        except OSError as exc:
            self._show_message(str(exc))
            return
        if keep_scroll:
            self._restore_scroll = self.grid_frame._parent_canvas.yview()[0]
        self._render(entries)

    def schedule_refresh(self) -> None:
        """Atualiza depois que a IA move um arquivo (só se a tela estiver aberta)."""
        if self.winfo_ismapped():
            self._debounce("refresh", 500, lambda: self.refresh(keep_scroll=True))

    def on_root_changed(self) -> None:
        self.parts = []
        if self.winfo_ismapped():
            self.refresh()

    # ----------------------------------------------------------------- grade

    def _render(self, entries: list) -> None:
        self._generation += 1
        self._cancel("batch")
        for card in self._cards:
            card.destroy()
        self._cards = []
        self._render_crumbs()
        self.back_button.configure(state="normal" if self.parts else "disabled")
        self.open_button.configure(state="normal")
        if not entries:
            self._show_message(t("lib.empty_folder") if self.parts else t("lib.empty_root"))
            return
        self.message.grid_remove()
        self.grid_frame.grid()
        self._columns = 0  # força o reposicionamento
        self._create_batch(entries, 0, self._generation)

    def _create_batch(self, entries: list, start: int, generation: int) -> None:
        if generation != self._generation:
            return  # o usuário já navegou para outra pasta
        depth = len(self.parts)
        for entry in entries[start:start + BATCH]:
            if entry.is_dir:
                # Só as categorias (nível 1) têm ícone temático
                emoji = category_icon(entry.name) if depth == 0 else FOLDER_ICON
                command = lambda name=entry.name: self.navigate(self.parts + [name])
            else:
                emoji = FILE_ICON
                command = lambda path=entry.path: self.app.open_path(path)
            self._cards.append(Card(self.grid_frame, self.app.icons.get(emoji, 52),
                                    emoji, entry.name, entry.detail, command))
        self._relayout(force=True)
        if start + BATCH < len(entries):
            self._jobs["batch"] = self.after(1, self._create_batch, entries,
                                             start + BATCH, generation)
        elif self._restore_scroll is not None:
            position, self._restore_scroll = self._restore_scroll, None
            self.after_idle(lambda: self.grid_frame._parent_canvas.yview_moveto(position))

    def _relayout(self, force: bool = False) -> None:
        width = self.grid_frame.winfo_width() / self.grid_frame._get_widget_scaling()
        columns = max(1, int((width + CARD_GAP) // (CARD_WIDTH + CARD_GAP)))
        if columns != self._columns:
            for index in range(max(columns, self._columns)):
                used = index < columns
                self.grid_frame.grid_columnconfigure(index, weight=1 if used else 0,
                                                     uniform="card" if used else "")
            self._columns = columns
            force = True
        if force:
            for index, card in enumerate(self._cards):
                card.grid(row=index // columns, column=index % columns,
                          padx=CARD_GAP // 2, pady=CARD_GAP // 2, sticky="nsew")

    def _render_crumbs(self) -> None:
        for widget in self.crumbs.winfo_children():
            widget.destroy()
        root = self.root()
        if root is None:
            return
        names = [root.name or str(root)] + self.parts
        # Corta nomes longos para a trilha caber na largura (~8 px por letra)
        available = self.crumbs.winfo_width() / self.crumbs._get_widget_scaling()
        limit = max(6, int(max(available, 240) / len(names) / 8) - 3)
        for depth, name in enumerate(names):
            if depth:
                ctk.CTkLabel(self.crumbs, text="›", font=theme.font(15),
                             text_color=theme.TEXT_MUTED).pack(side="left", padx=2)
            last = depth == len(names) - 1
            text = name if len(name) <= limit else name[:limit - 1] + "…"
            ctk.CTkButton(
                self.crumbs, text=text, width=24, height=30, corner_radius=8,
                font=theme.font(13, "bold" if last else "normal"),
                fg_color=theme.NAV_ACTIVE if last else "transparent",
                text_color=theme.NAV_ACTIVE_TEXT if last else theme.TEXT_MUTED,
                hover_color=theme.NAV_HOVER,
                command=lambda d=depth: self.navigate(self.parts[:d]),
            ).pack(side="left")

    def _show_message(self, text: str, with_button: bool = False) -> None:
        self._generation += 1
        self._cancel("batch")
        for card in self._cards:
            card.destroy()
        self._cards = []
        self._render_crumbs()
        self.back_button.configure(state="normal" if self.parts else "disabled")
        self.open_button.configure(state="normal" if self.current() and self.current().is_dir()
                                   else "disabled")
        self.grid_frame.grid_remove()
        self.message_text.configure(text=text)
        if with_button:
            self.message_button.grid(row=2, column=0, pady=(16, 0))
        else:
            self.message_button.grid_remove()
        self.message.grid(row=4, column=0, sticky="nsew")

    # ---------------------------------------------------------------- ações

    def _open_root(self) -> None:
        root = self.root()
        if root is None or not root.is_dir():
            self._show_message(t("lib.no_dest"), with_button=True)
            return
        self.app.open_path(root)

    def _open_current(self) -> None:
        current = self.current()
        if current is not None and current.is_dir():
            self.app.open_path(current)

    # -------------------------------------------------------------- after()

    def _debounce(self, name: str, delay_ms: int, func) -> None:
        self._cancel(name)

        def run() -> None:
            self._jobs.pop(name, None)
            func()

        self._jobs[name] = self.after(delay_ms, run)

    def _cancel(self, name: str) -> None:
        job = self._jobs.pop(name, None)
        if job is not None:
            self.after_cancel(job)

    def destroy(self) -> None:
        for job in list(self._jobs.values()):
            self.after_cancel(job)
        self._jobs.clear()
        super().destroy()
