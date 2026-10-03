"""Ícones da interface.

O Tk desenha emojis só em monocromático: ótimo para o menu lateral, onde o
ícone acompanha a cor do texto. Nos cards da Biblioteca o emoji é desenhado
colorido numa imagem com o Pillow, usando a fonte de emojis do Windows
(Segoe UI Emoji). Sem essa fonte (fora do Windows), os cards usam o emoji
como texto.

Regra visual da Biblioteca: só as categorias (nível 1) têm ícone temático.
Franquias e tipos de item usam a pasta genérica. Arquivos mostram a
miniatura; sem ela, o cubo de arquivo 3D (model_file_icon) ou a folha.
"""

import os
import re
import unicodedata
from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from sliceminddex.config import APP_ICON

FOLDER_ICON = "📁"
FILE_ICON = "📄"
DEFAULT_CATEGORY_ICON = "🗂"

# Palavras-chave (sem acento, minúsculas) -> ícone; a primeira que bater vence.
# Palavras de até 4 letras precisam ser a palavra inteira ("toy", "toys"),
# para "car" não pegar "cartoon"; as maiores valem como trecho ("filme").
_CATEGORY_RULES = (
    (("desconhecid", "unknown", "未知", "未识别"), "❔"),
    (("anime", "manga", "otaku", "动漫", "动画"), "🎎"),
    (("filme", "film", "serie", "movie", "cinema", "电影", "影视", "剧集"), "🎬"),
    (("jogo", "game", "gaming", "videogame", "游戏"), "🎮"),
    (("utilit", "ferrament", "tool", "工具", "实用"), "🛠"),
    (("automo", "carro", "veiculo", "vehicle", "moto", "汽车", "车辆"), "🚗"),
    (("cosplay", "capacete", "helmet", "mascara", "mask", "面具", "头盔"), "🎭"),
    (("miniatura", "miniature", "tabletop", "rpg", "warhammer", "dnd", "微缩", "桌游"), "🐉"),
    (("brinquedo", "toy", "玩具"), "🧸"),
    (("decor", "casa", "home", "装饰", "家居"), "🏠"),
    (("arte", "art", "escultura", "sculpt", "艺术", "雕塑"), "🎨"),
    (("educa", "ciencia", "science", "escola", "school", "教育", "科学"), "🔬"),
    (("musica", "music", "音乐"), "🎵"),
    (("esporte", "sport", "体育", "运动"), "⚽"),
    (("animal", "natureza", "nature", "pet", "动物", "自然"), "🐾"),
    (("eletron", "electron", "tecnolog", "technolog", "tech", "computador",
      "computer", "电子", "科技"), "💻"),
    (("cozinha", "kitchen", "culinaria", "厨房"), "🍳"),
    (("jardim", "garden", "planta", "plant", "花园", "植物"), "🌱"),
    (("joia", "jewel", "acessorio", "accessor", "moda", "fashion", "首饰",
      "饰品", "时尚"), "💍"),
    (("escritorio", "office", "papelaria", "办公"), "🗄"),
    (("robo", "robot", "机器人"), "🤖"),
    (("heroi", "superhero", "hero", "marvel", "英雄"), "🦸"),
    (("espaco", "space", "ficcao", "scifi", "太空", "科幻"), "🚀"),
    (("festa", "party", "natal", "christmas", "halloween", "节日"), "🎉"),
    (("geral", "general", "outros", "other", "misc", "其他", "综合"), "🧩"),
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def category_icon(name: str) -> str:
    """Ícone temático de uma categoria (pasta de nível 1)."""
    folded = _fold(name)
    words = set(re.split(r"[^0-9a-z]+", folded))
    for keywords, icon in _CATEGORY_RULES:
        for keyword in keywords:
            if keyword.isascii() and len(keyword) <= 4:
                if keyword in words or keyword + "s" in words:
                    return icon
            elif keyword in folded:
                return icon
    return DEFAULT_CATEGORY_ICON


@lru_cache(maxsize=1)
def _emoji_font() -> ImageFont.FreeTypeFont | None:
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguiemj.ttf")
    try:
        return ImageFont.truetype(path, 109)
    except OSError:
        return None


@lru_cache(maxsize=256)
def _emoji_pil(emoji: str) -> Image.Image | None:
    """Emoji colorido, recortado num quadrado transparente."""
    emoji_font = _emoji_font()
    if emoji_font is None:
        return None
    # Sem a libraqm o seletor de variação (U+FE0F) viraria um quadradinho
    char = emoji.replace("\ufe0f", "")
    canvas = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((80, 80), char, font=emoji_font,
                                embedded_color=True, anchor="mm")
    box = canvas.getbbox()
    if box is None:
        return None
    glyph = canvas.crop(box)
    side = max(glyph.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(glyph, ((side - glyph.width) // 2, (side - glyph.height) // 2))
    return square


@lru_cache(maxsize=16)
def model_file_icon(extension: str, dark: bool) -> Image.Image:
    """Ícone genérico de arquivo 3D (sem miniatura): cubo verde com a extensão.

    Desenhado em 512 px e reduzido para 256 px, o que suaviza as bordas.
    """
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    cx, cy, s = 256, 214, 150
    dx = s * 0.866  # cos 30°: projeção isométrica
    top, center, bottom = (cx, cy - s), (cx, cy), (cx, cy + s)
    left_top, right_top = (cx - dx, cy - s / 2), (cx + dx, cy - s / 2)
    left_bottom, right_bottom = (cx - dx, cy + s / 2), (cx + dx, cy + s / 2)
    draw.polygon([top, right_top, center, left_top], fill="#4ADE80")
    draw.polygon([left_top, center, bottom, left_bottom], fill="#00AE42")
    draw.polygon([center, right_top, right_bottom, bottom], fill="#00843A")
    for end in (left_top, right_top, bottom):  # arestas da frente, em destaque
        draw.line([center, end], fill=(255, 255, 255, 110), width=6)

    label = extension.lstrip(".").upper()
    try:
        font = ImageFont.truetype("segoeuib.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    left, _, right, _ = draw.textbbox((0, 0), label, font=font)
    width = right - left + 64
    pill = (cx - width / 2, 404, cx + width / 2, 484)
    draw.rounded_rectangle(pill, radius=40, fill="#E8EAED" if dark else "#15171A")
    draw.text((cx, 444), label, font=font, anchor="mm", fill="#15171A" if dark else "#FFFFFF")
    return canvas.resize((256, 256), Image.Resampling.LANCZOS)


@lru_cache(maxsize=1)
def app_icon_image() -> Image.Image | None:
    """O maior quadro do app_icon.ico (256 px), ou None se o arquivo faltar."""
    try:
        with Image.open(APP_ICON) as icon:
            icon.size = max(icon.ico.sizes())
            return icon.convert("RGBA")
    except (OSError, AttributeError, ValueError):
        return None


class IconCache:
    """Imagens de emoji (e do ícone do app) por tamanho.

    Um cache por janela: as imagens do Tk pertencem à janela que as criou.
    """

    def __init__(self) -> None:
        self._images: dict[tuple[str, int], ctk.CTkImage | None] = {}

    def get(self, emoji: str, size: int) -> ctk.CTkImage | None:
        return self._cached(emoji, size, lambda: _emoji_pil(emoji))

    def app_icon(self, size: int) -> ctk.CTkImage | None:
        return self._cached("<app_icon>", size, app_icon_image)

    def model_file(self, extension: str, size: int) -> ctk.CTkImage:
        """Ícone genérico de arquivo 3D, nas versões clara e escura."""
        key = (f"<model>{extension}", size)
        if key not in self._images:
            self._images[key] = ctk.CTkImage(model_file_icon(extension, dark=False),
                                             model_file_icon(extension, dark=True),
                                             size=(size, size))
        return self._images[key]

    def _cached(self, name: str, size: int, load) -> ctk.CTkImage | None:
        key = (name, size)
        if key not in self._images:
            image = load()
            self._images[key] = (ctk.CTkImage(image, image, size=(size, size))
                                 if image else None)
        return self._images[key]
