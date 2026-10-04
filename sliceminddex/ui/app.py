"""Janela principal do SliceMind DEX: menu lateral + Painel, Biblioteca e Configurações.

A janela é o "controlador": guarda as configurações (SQLite), o idioma, o
tema e o histórico do log, e liga as telas ao serviço de monitoramento
(core/service.py), que continua rodando mesmo quando as telas são recriadas
(ex.: ao trocar o idioma).

Thread-safety: o Tkinter só pode ser manipulado pela thread principal. O
serviço avisa de outras threads (Watchdog, verificadora, pool da IA); esses
avisos entram em `self._ui_queue`, que a thread principal esvazia via after().
"""

import ctypes
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import tkinter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from sliceminddex import locales
from sliceminddex.config import (
    APP_ICON,
    APP_NAME,
    DEFAULT_DEST_DIR,
    DEFAULT_LANGUAGE,
    DEFAULT_THEME,
    PREVIOUS_DEFAULT_DEST_DIR,
    THEMES,
    with_prints_folder,
)
from sliceminddex.core.calculator import CURRENCIES, DEFAULT_CURRENCY
from sliceminddex.core.database import FIELDS, SettingsDB
from sliceminddex.core.service import MonitorService, Stats
from sliceminddex.locales import Msg, t
from sliceminddex.ui import theme
from sliceminddex.ui.api_key_help import ApiKeyRequiredDialog, ApiTutorialWindow
from sliceminddex.ui.calculator import CalculatorView
from sliceminddex.ui.dashboard import DashboardView
from sliceminddex.ui.icons import IconCache
from sliceminddex.ui.library import LibraryView
from sliceminddex.ui.onboarding import OnboardingDialog
from sliceminddex.ui.settings import SettingsView
from sliceminddex.ui.sidebar import Sidebar
from sliceminddex.ui.thumbnails import ThumbnailLoader
from sliceminddex.ui.tray import TrayIcon
from sliceminddex.ui.tray import available as tray_available

UI_POLL_MS = 100
LOG_HISTORY = 1000
MIN_SIZE = (640, 560)   # cabe em monitor em pé (9:16) com escala de 150%
COMPACT_BELOW = 980     # largura (sem escala de DPI) em que o menu vira só ícones

# Campos da calculadora (compartilhados pelos modos Simples e Avançado)
CALC_FIELDS = ("price_kg", "weight", "hours", "tariff", "power", "margin", "machine",
               "lifetime", "labor_rate", "labor_hours", "quantity", "risk")
# Os que quase não mudam entre orçamentos ficam salvos no banco (campo -> coluna)
CALC_SAVED = {"price_kg": "calc_preco_kg", "power": "calc_potencia",
              "tariff": "calc_tarifa", "machine": "calc_valor_maquina",
              "lifetime": "calc_vida_util", "labor_rate": "calc_hora_trabalho"}
CALC_SAVE_DELAY_MS = 800  # salva depois que o usuário para de digitar

ctk.set_default_color_theme("green")


def _same_path(a: str | os.PathLike, b: str | os.PathLike) -> bool:
    """Compara caminhos como o Windows: sem diferenciar maiúsculas e barras."""
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def _set_taskbar_identity() -> None:
    """Rodando pelo código (python.exe), a barra de tarefas mostraria o ícone
    do Python; com um AppUserModelID próprio ela usa o ícone da janela. No
    .exe não é preciso: o Windows já usa o ícone embutido nele."""
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SliceMindDex.App")
        except (AttributeError, OSError):
            pass


class SliceMindDexApp(ctk.CTk):
    def __init__(self) -> None:
        _set_taskbar_identity()  # antes de a janela existir
        super().__init__()
        self.title(APP_NAME)
        self._set_window_icon()
        self.minsize(*MIN_SIZE)
        self._place_window(1240, 800)
        self.configure(fg_color=theme.WINDOW_BG)

        self.source_var = ctk.StringVar()
        self.dest_var = ctk.StringVar()
        self.api_key_var = ctk.StringVar()
        # Últimos valores gravados no banco (evita salvar sem mudança)
        self._saved: dict[str, str] = dict.fromkeys(FIELDS, "")
        self.db: SettingsDB | None = None
        self.theme = DEFAULT_THEME
        self.currency = DEFAULT_CURRENCY
        self.icons = IconCache()
        # Miniaturas da Biblioteca: o cache sobrevive à troca de idioma
        self.thumbnails = ThumbnailLoader(self._call_ui)
        # Calculadora: as variáveis são do app (sobrevivem à troca de idioma)
        self.calc_vars = {name: ctk.StringVar() for name in CALC_FIELDS}
        self.calc_vars["quantity"].set("1")
        self.calc_mode = "simple"
        self._calc_save_job: str | None = None

        self.log_records: list[tuple[str, Msg]] = []
        self._ui_queue: queue.Queue[tuple[Callable, tuple]] = queue.Queue()
        self._ui_poll_id: str | None = None
        self._resize_job: str | None = None
        self._compact: bool | None = None
        self._view = "dashboard"
        self.sidebar: Sidebar | None = None
        self.views: dict[str, ctk.CTkFrame] = {}
        self.tray: TrayIcon | None = None
        self._tray_hint_shown = False
        # Janelas de ajuda da API Key (uma de cada por vez)
        self._api_dialog: ApiKeyRequiredDialog | None = None
        self._tutorial: ApiTutorialWindow | None = None

        self.service = MonitorService(
            on_log=self.log,
            on_state=lambda state: self._call_ui(self._on_state, state),
            on_stats=lambda stats: self._call_ui(self._on_stats, stats),
            on_organized=lambda _result: self._call_ui(self._on_organized),
        )

        self.log(Msg("log.app_started"))
        self._load_settings()  # define idioma e tema antes de montar as telas

        # Primeira execução (ou pastas não configuradas): assistente modal com
        # a janela principal escondida. Bandeja e Watchdog só começam depois.
        self.cancelled = False
        if not self.source_var.get().strip() or not self.dest_var.get().strip():
            self.withdraw()
            dialog = OnboardingDialog(self)
            self.wait_window(dialog)
            if not dialog.completed:  # "Sair do SliceMind DEX" no assistente
                self.cancelled = True
                self.destroy()
                return
            # Escondida antes de aparecer, o CustomTkinter não a mostra sozinho
            self.deiconify()
        self._build_ui()

        # Bandeja: o X e o minimizar escondem a janela e o monitoramento
        # continua; "Sair" (menu do ícone ou menu lateral) encerra de vez
        if tray_available():
            self.tray = TrayIcon(self)
            self.tray.start()
            self.tray.update(self.service.state)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray if self.tray else self.quit_app)
        self.bind("<Unmap>", self._on_unmap, add="+")
        self.bind("<Configure>", self._on_resize, add="+")
        self._process_ui_queue()

    # ---------------------------------------------------------------- telas

    @property
    def dashboard(self) -> DashboardView:
        return self.views["dashboard"]

    @property
    def library(self) -> LibraryView:
        return self.views["library"]

    @property
    def settings(self) -> SettingsView:
        return self.views["settings"]

    def _build_ui(self, library_parts: list[str] | None = None) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, self)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.views = {
            "dashboard": DashboardView(self.content, self),
            "library": LibraryView(self.content, self),
            "calculator": CalculatorView(self.content, self),
            "settings": SettingsView(self.content, self),
        }
        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")
            view.grid_remove()
        self.library.parts = list(library_parts or [])

        self.dashboard.render_log(self.log_records)
        self.dashboard.refresh_paths()
        self._on_state(self.service.state)
        self._on_stats(self.service.stats())
        self._compact = None
        self._apply_layout()
        self.show_view(self._view)

    def _rebuild_ui(self) -> None:
        """Recria as telas (troca de idioma); o monitoramento não é afetado."""
        parts = list(self.library.parts)
        self.sidebar.destroy()
        self.content.destroy()
        self._build_ui(library_parts=parts)

    def show_view(self, name: str) -> None:
        self._view = name
        for key, view in self.views.items():
            if key == name:
                view.grid()
            else:
                view.grid_remove()
        self.sidebar.set_active(name)
        if name == "library":
            self.library.refresh()

    def _on_resize(self, event) -> None:
        if event.widget is not self:  # o <Configure> da raiz chega de todo filho
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._apply_layout)

    def _apply_layout(self) -> None:
        """Menu só de ícones e margens menores em janelas estreitas."""
        self._resize_job = None
        width = self.winfo_width() / self._get_window_scaling()
        compact = 1 < width < COMPACT_BELOW
        if compact == self._compact:
            return
        self._compact = compact
        self.sidebar.set_compact(compact)
        self.content.grid(padx=16 if compact else 32, pady=16 if compact else 26)

    def _set_window_icon(self) -> None:
        """Ícone da barra de título e da barra de tarefas (app_icon.ico).

        Chamado logo no início: o CustomTkinter só põe o ícone padrão dele
        se o app não tiver definido um. "default" vale também para janelas
        abertas depois. Sem o arquivo, fica o ícone padrão.
        """
        if sys.platform != "win32" or not APP_ICON.is_file():
            return
        try:
            self.iconbitmap(str(APP_ICON))
            self.iconbitmap(default=str(APP_ICON))
        except tkinter.TclError:
            pass

    def _place_window(self, width: int, height: int) -> None:
        """Centraliza a janela, sem passar do tamanho da tela."""
        scale = self._get_window_scaling()
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = max(MIN_SIZE[0], min(width, int(screen_w / scale * 0.92)))
        height = max(MIN_SIZE[1], min(height, int(screen_h / scale * 0.88)))
        x = max(0, (screen_w - int(width * scale)) // 2)
        y = max(0, (screen_h - int(height * scale)) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")  # o CTk escala só a largura/altura

    # ------------------------------------------------------- threads -> UI

    def _call_ui(self, func: Callable, *args) -> None:
        """Executa na thread principal: já, se estiver nela; senão, pela fila."""
        if threading.current_thread() is threading.main_thread():
            func(*args)
        else:
            self._ui_queue.put((func, args))

    def _process_ui_queue(self) -> None:
        # Reagenda antes de processar: uma exceção não interrompe o loop
        self._ui_poll_id = self.after(UI_POLL_MS, self._process_ui_queue)
        while True:
            try:
                func, args = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            func(*args)

    def log(self, msg: Msg) -> None:
        """Acrescenta uma linha ao log (seguro em qualquer thread).

        O horário é capturado aqui, no momento do evento. Na thread principal
        (respostas a cliques) a linha entra na hora; a fila só é processada
        quando o clique termina. Assim "Monitoramento iniciado" aparece antes
        do resultado da varredura, que outra thread dispara durante o clique.
        """
        record = (datetime.now().strftime("%H:%M:%S"), msg)
        self._call_ui(self._add_log, record)

    def _add_log(self, record: tuple[str, Msg]) -> None:
        self.log_records.append(record)
        del self.log_records[:-LOG_HISTORY]
        if self.views:
            self.dashboard.append_log(record)

    def clear_log(self) -> None:
        self.log_records.clear()
        self.dashboard.render_log([])

    def _on_state(self, state: str) -> None:
        if self.tray:
            self.tray.update(state)  # também atualiza os textos ao trocar o idioma
        if not self.views:
            return
        self.sidebar.set_status(state)
        self.dashboard.set_state(state)
        # Trocar de pasta durante o monitoramento não teria efeito no Watchdog
        self.settings.set_locked(state != "stopped")

    def _on_stats(self, stats: Stats) -> None:
        if self.views:
            self.dashboard.set_stats(stats)

    def _on_organized(self) -> None:
        if self.views:
            self.library.schedule_refresh()

    # -------------------------------------------------------- preferências

    def set_language(self, code: str) -> None:
        if code == locales.get_language():
            return
        locales.set_language(code)
        self._persist(idioma=code)
        self._rebuild_ui()

    def set_currency(self, code: str) -> None:
        if code not in CURRENCIES or code == self.currency:
            return
        self.currency = code
        self._persist(moeda=code)
        if self.views:
            self.views["calculator"].apply_currency()

    def _schedule_calc_save(self) -> None:
        if self._calc_save_job is not None:
            self.after_cancel(self._calc_save_job)
        self._calc_save_job = self.after(CALC_SAVE_DELAY_MS, self._save_calc_values)

    def _save_calc_values(self) -> None:
        """Grava os valores fixos da calculadora que mudaram (como digitados)."""
        self._calc_save_job = None
        changed = {column: self.calc_vars[name].get().strip()
                   for name, column in CALC_SAVED.items()
                   if self.calc_vars[name].get().strip() != self._saved[column]}
        if changed:
            self._persist(**changed)

    def set_theme(self, mode: str) -> None:
        if mode not in THEMES or mode == self.theme:
            return
        self.theme = mode
        ctk.set_appearance_mode(mode)
        self._persist(tema=mode)

    def _persist(self, **values: str) -> bool:
        """Grava no SQLite e registra erros no log. Retorna True se gravou."""
        if self.db is None:
            self.log(Msg("log.db_unavailable"))
            return False
        try:
            self.db.save(**values)
        except sqlite3.Error as exc:
            self.log(Msg("log.db_save_error", error=str(exc)))
            return False
        self._saved.update(values)
        return True

    def _load_settings(self) -> None:
        try:
            self.db = SettingsDB()
            settings = self.db.load()
        except (sqlite3.Error, OSError) as exc:
            self.log(Msg("log.db_open_error", error=str(exc)))
            ctk.set_appearance_mode(self.theme)
            return

        if self.db.migrated_from is not None:
            self.log(Msg("log.db_migrated", old=str(self.db.migrated_from),
                         new=str(self.db.db_path)))
        self._saved.update(settings)

        # Idioma salvo; na primeira vez, o escolhido no instalador (ou inglês)
        locales.set_language(settings["idioma"] or locales.installer_language()
                             or DEFAULT_LANGUAGE)
        if not settings["idioma"]:
            self._persist(idioma=locales.get_language())
        self.theme = settings["tema"] if settings["tema"] in THEMES else DEFAULT_THEME
        ctk.set_appearance_mode(self.theme)
        self.currency = settings["moeda"] if settings["moeda"] in CURRENCIES else DEFAULT_CURRENCY

        # Calculadora: carrega os valores fixos e salva sozinho quando mudarem
        for name, column in CALC_SAVED.items():
            self.calc_vars[name].set(settings[column])
            self.calc_vars[name].trace_add("write", lambda *_: self._schedule_calc_save())

        self.source_var.set(settings["pasta_origem"])
        self.dest_var.set(settings["pasta_destino"])
        self.api_key_var.set(settings["api_key"])
        if any(settings[field] for field in ("pasta_origem", "pasta_destino", "api_key")):
            self.log(Msg("log.settings_loaded"))
        else:
            self.log(Msg("log.first_run", path=str(self.db.db_path.parent)))

        dest = settings["pasta_destino"]
        if not dest:
            self._apply_default_dest()
        elif (_same_path(dest, PREVIOUS_DEFAULT_DEST_DIR)
              and not _same_path(dest, DEFAULT_DEST_DIR)):
            # Ainda no padrão antigo (Documentos): passa para o novo padrão
            self._apply_default_dest(previous=dest)
        else:
            # Destinos salvos por versões anteriores ganham a subpasta PRINTS
            self.commit_folder("pasta_destino")

    def _apply_default_dest(self, previous: str | None = None) -> None:
        """Usa a pasta padrão (Program Files (x86)\\SliceMind DEX\\PRINTS, criada
        pelo instalador com permissão de escrita para os usuários).

        `previous` é o destino antigo quando o usuário ainda estava no padrão
        de versões anteriores; ele continua valendo se a pasta nova não estiver
        disponível (ex.: SliceMind DEX ainda não instalado).
        """
        path = str(DEFAULT_DEST_DIR)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            self.log(Msg("log.default_dest_error", error=str(exc)))
            return
        self.dest_var.set(path)
        if not self._persist(pasta_destino=path):
            return
        if previous:
            self.log(Msg("log.default_dest_changed", path=path))
            self.log(Msg("log.old_files_remain", path=previous))
        else:
            self.log(Msg("log.default_dest_created", path=path))

    # -------------------------------------------------------------- pastas

    def _var(self, field: str) -> ctk.StringVar:
        return self.source_var if field == "pasta_origem" else self.dest_var

    def _ensure_prints_dir(self, path: str) -> bool:
        """Cria a pasta PRINTS se a pasta escolhida pelo usuário existir (a
        padrão é recriada por inteiro)."""
        base = os.path.dirname(path)
        if not os.path.isdir(base) and not _same_path(path, DEFAULT_DEST_DIR):
            self.log(Msg("log.dest_not_found", path=base))
            return False
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            self.log(Msg("log.create_error", path=path, error=str(exc)))
            return False
        return True

    def browse_folder(self, field: str) -> None:
        var = self._var(field)
        current = var.get().strip()
        folder = filedialog.askdirectory(
            parent=self, title=t(f"field.{field}"),
            initialdir=current if os.path.isdir(current) else None,
        )
        if folder:  # vazio quando o usuário cancela
            var.set(os.path.normpath(folder))
            self.commit_folder(field)

    def commit_folder(self, field: str) -> None:
        var = self._var(field)
        path = var.get().strip()
        if path:
            path = os.path.normpath(path)
            if field == "pasta_destino":
                # A árvore da IA sempre fica dentro de <escolha>/PRINTS
                path = with_prints_folder(path)
            var.set(path)
        if path == self._saved[field]:
            return

        label = Msg(f"field.{field}")
        if path:
            if field == "pasta_destino":
                if not self._ensure_prints_dir(path):
                    return
            elif not os.path.isdir(path):
                self.log(Msg("log.folder_not_found", field=label, path=path))
                return

        if self._persist(**{field: path}):
            if path:
                self.log(Msg("log.folder_saved", field=label, path=path))
            else:
                self.log(Msg("log.folder_removed", field=label))
            self._paths_changed(field)

    def _paths_changed(self, field: str) -> None:
        if not self.views:
            return
        self.dashboard.refresh_paths()
        if field == "pasta_destino":
            self.library.on_root_changed()

    def save_api_key(self) -> None:
        api_key = self.api_key_var.get().strip()
        self.api_key_var.set(api_key)
        if api_key == self._saved["api_key"]:
            self.log(Msg("log.api_key_unchanged"))
            return
        # Nunca registrar a chave em si no log
        if self._persist(api_key=api_key):
            self.log(Msg("log.api_key_saved" if api_key else "log.api_key_removed"))

    # ------------------------------------------------------- monitoramento

    def start_monitoring(self) -> None:
        # Garante que caminhos digitados (sem Enter) sejam validados e salvos
        self.commit_folder("pasta_origem")
        self.commit_folder("pasta_destino")

        source = self.source_var.get()
        dest = self.dest_var.get()
        api_key = self.api_key_var.get().strip()

        # Sem a chave a IA não funciona: em vez de só um erro no log, um aviso
        # explica e leva direto ao campo (muita gente nunca ouviu falar dela)
        if not api_key:
            self.ask_api_key()
            return
        missing = [Msg(f"field.{field}") for field, value in (
            ("pasta_origem", source), ("pasta_destino", dest),
        ) if not value]
        if missing:
            self.log(Msg("log.start_missing", fields=missing))
            return
        if not os.path.isdir(source):
            self.log(Msg("log.source_not_found", path=source))
            return
        # Recria a PRINTS caso tenha sido apagada desde que foi salva
        if not self._ensure_prints_dir(dest):
            return

        try:
            self.service.start(source, dest, api_key)
        except Exception as exc:
            self.log(Msg("log.start_error", error=str(exc)))
            return
        self.log(Msg("log.monitor_started", path=source))

    def stop_monitoring(self) -> None:
        self.service.stop()

    # ------------------------------------------------------------ API Key

    def ask_api_key(self) -> None:
        """Aviso de que falta a API Key, com o botão "Adicionar API"."""
        if self._api_dialog is not None and self._api_dialog.winfo_exists():
            self._api_dialog.bring_to_front()
            return
        if self.state() in ("withdrawn", "iconic"):  # iniciado pela bandeja
            self.show_window()
        self._api_dialog = ApiKeyRequiredDialog(self)

    def open_api_key_settings(self) -> None:
        """Configurações, com o cursor já no campo da API Key."""
        self.show_view("settings")
        self.settings.focus_api_key()

    def open_api_tutorial(self) -> None:
        """Janela "Como obter sua API Key" (uma só, mesmo clicando de novo)."""
        if self._tutorial is not None and self._tutorial.winfo_exists():
            self._tutorial.show()
            return
        self._tutorial = ApiTutorialWindow(self)

    # --------------------------------------------------------------- ações

    def open_path(self, path: str | Path) -> None:
        """Abre um arquivo ou pasta no programa padrão (Explorer, fatiador...)."""
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as exc:
            self.log(Msg("log.open_error", path=str(path), error=str(exc)))

    # ------------------------------------------------------------- bandeja

    def request_show(self) -> None:
        """Mostra a janela (seguro em qualquer thread: bandeja, 2ª instância)."""
        self._call_ui(self.show_window)

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        # O Windows nem sempre deixa trazer a janela para a frente; o topmost
        # momentâneo garante que ela apareça acima das outras
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def hide_to_tray(self) -> None:
        """Esconde a janela (sai da barra de tarefas); o monitoramento segue."""
        self.withdraw()
        if not self._tray_hint_shown:  # avisa uma vez por sessão onde o app foi parar
            self._tray_hint_shown = True
            self.tray.notify(t("tray.hint"))

    def _on_unmap(self, event) -> None:
        # Minimizar também manda para a bandeja (o <Unmap> da raiz chega de
        # todo filho; "iconic" = minimizada, não escondida pelo próprio app)
        if event.widget is self and self.tray and self.state() == "iconic":
            self.after_idle(self.hide_to_tray)

    def toggle_monitoring(self) -> None:
        """Iniciar/Parar pelo menu da bandeja."""
        if self.service.state == "running":
            self.stop_monitoring()
        elif self.service.state == "stopped":
            self.start_monitoring()
            asking_key = self._api_dialog is not None and self._api_dialog.winfo_exists()
            if self.service.state != "running" and not asking_key:
                self.show_view("dashboard")  # não iniciou: o motivo está no log
                self.show_window()

    def quit_app(self) -> None:
        """Encerra de vez: para o Watchdog, tira o ícone da bandeja e fecha.

        Cancela o que está na fila; tarefas já em andamento terminam.
        """
        if self._calc_save_job is not None:  # não perde o que acabou de ser digitado
            self.after_cancel(self._calc_save_job)
            self._save_calc_values()
        self.service.shutdown(timeout=2.0)
        if self.tray:
            self.tray.stop()
        if self._ui_poll_id is not None:
            self.after_cancel(self._ui_poll_id)
        self.destroy()
