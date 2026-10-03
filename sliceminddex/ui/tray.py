"""Ícone na bandeja do Windows (área de notificação, perto do relógio).

O pystray roda o próprio loop de mensagens numa thread dedicada. As ações do
menu chegam nessa thread e são repassadas à thread do Tk pela fila da janela
(`app._call_ui`), como todo evento que vem de fora da interface.

Clique (simples ou duplo) no ícone: abre a janela. Botão direito: menu.
"""

import threading

from PIL import Image, ImageDraw

from sliceminddex.config import APP_NAME
from sliceminddex.locales import t
from sliceminddex.ui.icons import app_icon_image

try:
    import pystray
except ImportError:  # sem o pystray, o app funciona como antes (X encerra)
    pystray = None

ICON_SIZE = 64
# Selo no canto do ícone: verde monitorando, laranja parando, sem selo parado
_BADGES = {"running": (52, 210, 123, 255), "stopping": (255, 181, 71, 255)}


def available() -> bool:
    return pystray is not None


class TrayIcon:
    def __init__(self, app) -> None:
        self.app = app
        self._state = "stopped"
        self._images: dict[str, Image.Image] = {}
        self._icon = pystray.Icon(
            APP_NAME, self._image("stopped"), APP_NAME,
            menu=pystray.Menu(
                # default=True: ação do clique (simples ou duplo) no ícone
                pystray.MenuItem(lambda _item: t("tray.open"), self._open, default=True),
                pystray.MenuItem(lambda _item: f"● {t('tray.status', status=t(f'status.{self._state}'))}",
                                 None, enabled=False),
                pystray.MenuItem(lambda _item: t("dash.stop") if self._state == "running"
                                 else t("dash.start"),
                                 self._toggle, enabled=lambda _item: self._state != "stopping"),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(lambda _item: t("tray.exit"), self._exit),
            ),
        )
        self._thread = threading.Thread(target=self._icon.run, name="SliceMindDex-Tray",
                                        daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._icon.stop()

    def update(self, state: str) -> None:
        """Novo estado do monitoramento (ou novo idioma): ícone, dica e menu."""
        self._state = state
        self._icon.icon = self._image(state)
        self._icon.title = f"{APP_NAME} — {t(f'status.{state}')}"
        # Antes de aparecer, o pystray ainda vai montar o menu com os textos atuais
        if self._icon.visible:
            self._icon.update_menu()

    def notify(self, message: str) -> None:
        """Balão/notificação do Windows saindo do ícone."""
        if self._icon.HAS_NOTIFICATION:
            try:
                self._icon.notify(message, APP_NAME)
            except Exception:  # notificação é só um aviso: nunca derruba o app
                pass

    # Ações do menu (rodam na thread do pystray)

    def _open(self, _icon=None, _item=None) -> None:
        self.app.request_show()

    def _toggle(self, _icon=None, _item=None) -> None:
        self.app._call_ui(self.app.toggle_monitoring)

    def _exit(self, _icon=None, _item=None) -> None:
        self.app._call_ui(self.app.quit_app)

    def _image(self, state: str) -> Image.Image:
        if state not in self._images:
            base = app_icon_image()
            image = (base.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS) if base
                     else Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 168, 70, 255)))
            color = _BADGES.get(state)
            if color:
                draw = ImageDraw.Draw(image)
                size, ring = 28, 4
                left = top = ICON_SIZE - size
                draw.ellipse((left - ring, top - ring, ICON_SIZE, ICON_SIZE),
                             fill=(24, 26, 30, 255))  # contorno escuro: destaca o selo
                draw.ellipse((left, top, ICON_SIZE - ring, ICON_SIZE - ring), fill=color)
            self._images[state] = image
        return self._images[state]
