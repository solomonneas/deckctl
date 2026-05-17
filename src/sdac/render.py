"""Pillow-based icon renderer.

Produces 72x72 RGB images suitable for the Stream Deck MK.2 (which expects
72x72 JPEG; conversion happens at device-push time in a later phase).

Pure: takes a KeyConfig + state, returns a PIL Image. No file I/O except
loading bundled fonts and user-specified image references.
"""

from __future__ import annotations

import io
from importlib.resources import files
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from sdac.config import IconSpec, KeyConfig
from sdac.errors import RenderError

KEY_SIZE = 72  # MK.2 spec
DEFAULT_BG = "#000000"
DEFAULT_FG = "#ffffff"
FONT_RESOURCE = files("sdac.assets.fonts").joinpath("Inter-Bold.ttf")

State = Literal["idle", "active", "pressed", "error", "disconnected"]


def _bg_color(icon: IconSpec, state: State) -> str:
    """Resolve background color for a given state, with fallback chain."""
    match state:
        case "idle":
            return icon.bg_idle or icon.bg or DEFAULT_BG
        case "active":
            return icon.bg_active or icon.bg_idle or icon.bg or DEFAULT_BG
        case "pressed":
            return icon.bg_pressed or icon.bg_idle or icon.bg or DEFAULT_BG
        case "error":
            return icon.bg_error or "#b71c1c"
        case "disconnected":
            return icon.bg_disconnected or "#424242"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        data = FONT_RESOURCE.read_bytes()
        return ImageFont.truetype(io.BytesIO(data), size=size)
    except OSError as e:
        raise RenderError(f"cannot load bundled font: {e}") from e


def render_key(key: KeyConfig, *, state: State = "idle") -> Image.Image:
    """Render a single key icon at native MK.2 resolution."""
    bg = _bg_color(key.icon, state)
    fg = key.icon.fg or DEFAULT_FG
    img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), bg)
    draw = ImageDraw.Draw(img)
    if key.icon.text:
        _draw_text(draw, key.icon.text, fg)
    return img


def _draw_text(draw: ImageDraw.ImageDraw, text: str, fg: str) -> None:
    """Draw centered, auto-sized text within KEY_SIZE with 4px padding."""
    for size in range(18, 8, -1):
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= KEY_SIZE - 8 and h <= KEY_SIZE - 8:
            x = (KEY_SIZE - w) // 2 - bbox[0]
            y = (KEY_SIZE - h) // 2 - bbox[1]
            draw.text((x, y), text, fill=fg, font=font)
            return
    font = _load_font(9)
    draw.text((4, 4), text[:8], fill=fg, font=font)
