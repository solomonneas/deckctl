"""Pillow-based icon renderer.

Produces 72x72 RGB images suitable for the Stream Deck MK.2 (which expects
72x72 JPEG; conversion happens at device-push time in a later phase).

Pure: takes a KeyConfig + state, returns a PIL Image. No file I/O except
loading bundled fonts and user-specified image references.
"""

from __future__ import annotations

import io
from importlib.resources import files
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji  # type: ignore[import-untyped]

from deckctl.config import IconSpec, KeyConfig, PageConfig
from deckctl.errors import RenderError

KEY_SIZE = 72  # MK.2 spec
MK2_COLS = 5
MK2_ROWS = 3
MOSAIC_GAP = 8
PLACEHOLDER_BG = "#000000"
DEFAULT_BG = "#000000"
DEFAULT_FG = "#ffffff"
FONT_RESOURCE = files("deckctl.assets.fonts").joinpath("Inter-Bold.ttf")

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
    if key.icon.image:
        _composite_image(img, key.icon.image)
    if key.icon.emoji and key.icon.text:
        _draw_emoji_and_text(img, key.icon.emoji, key.icon.text, fg)
    elif key.icon.emoji:
        _draw_emoji_only(img, key.icon.emoji)
    elif key.icon.text:
        _draw_text(ImageDraw.Draw(img), key.icon.text, fg)
    return img


def _composite_image(canvas: Image.Image, path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise RenderError(f"icon image not found: {p}")
    try:
        src = Image.open(p).convert("RGBA")
    except OSError as e:
        raise RenderError(f"cannot read icon image {p}: {e}") from e
    src.thumbnail((KEY_SIZE - 8, KEY_SIZE - 8), Image.Resampling.LANCZOS)
    x = (KEY_SIZE - src.width) // 2
    y = (KEY_SIZE - src.height) // 2
    canvas.paste(src, (x, y), src)


def _draw_emoji_only(img: Image.Image, emoji: str) -> None:
    """Emoji centered at 40px."""
    size = 40
    font = _load_font(size)
    with Pilmoji(img) as p:
        bbox = p.getsize(emoji, font=font)
        x = (KEY_SIZE - bbox[0]) // 2
        y = (KEY_SIZE - bbox[1]) // 2
        p.text((x, y), emoji, font=font)


def _draw_emoji_and_text(img: Image.Image, emoji: str, text: str, fg: str) -> None:
    """Layout: emoji on top half (~28px), text on bottom half (auto-sized)."""
    emoji_font = _load_font(28)
    with Pilmoji(img) as p:
        bbox = p.getsize(emoji, font=emoji_font)
        x = (KEY_SIZE - bbox[0]) // 2
        y = 6
        p.text((x, y), emoji, font=emoji_font)
    draw = ImageDraw.Draw(img)
    for size in range(14, 8, -1):
        font = _load_font(size)
        bbox2 = draw.textbbox((0, 0), text, font=font)
        w = bbox2[2] - bbox2[0]
        h = bbox2[3] - bbox2[1]
        if w <= KEY_SIZE - 4 and h <= 22:
            x = int((KEY_SIZE - w) // 2 - bbox2[0])
            y = int(KEY_SIZE - h - 6 - bbox2[1])
            draw.text((x, y), text, fill=fg, font=font)
            return
    font = _load_font(9)
    draw.text((4, KEY_SIZE - 14), text[:7], fill=fg, font=font)


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


def render_mosaic(page: PageConfig, *, state: State = "idle") -> Image.Image:
    """Compose every key on a page into a single mosaic image.

    Empty key slots render as solid black tiles (the placeholder background).
    Output dimensions: 5*72 + 4*8 = 392 wide, 3*72 + 2*8 = 232 tall.
    """
    w = KEY_SIZE * MK2_COLS + (MK2_COLS - 1) * MOSAIC_GAP
    h = KEY_SIZE * MK2_ROWS + (MK2_ROWS - 1) * MOSAIC_GAP
    canvas = Image.new("RGB", (w, h), PLACEHOLDER_BG)
    for idx in range(MK2_COLS * MK2_ROWS):
        row = idx // MK2_COLS
        col = idx % MK2_COLS
        x = col * (KEY_SIZE + MOSAIC_GAP)
        y = row * (KEY_SIZE + MOSAIC_GAP)
        key = page.keys.get(idx)
        if key is not None:
            tile = render_key(key, state=state)
            canvas.paste(tile, (x, y))
    return canvas
