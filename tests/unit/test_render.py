"""Renderer tests. Uses golden images.

Regenerate goldens by running:
    DECKCTL_REGEN=1 pytest tests/unit/test_render.py
Review the resulting PNGs in tests/fixtures/goldens/ before committing.

Goldens were generated on Linux with the system Pillow + freetype. They do
not match Windows-generated output pixel-for-pixel (different freetype
build), so golden-comparison tests are skipped on Windows. The renderer
code path is exercised on Windows by the dimensions / structure tests
that don't compare against goldens.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from deckctl.config import IconSpec, KeyConfig, ShellAction, load_config
from deckctl.render import KEY_SIZE, MK2_COLS, MK2_ROWS, render_key, render_mosaic

GOLDENS = Path(__file__).parent.parent / "fixtures" / "goldens"
REGEN = os.environ.get("DECKCTL_REGEN") == "1"
WINDOWS = sys.platform.startswith("win")
SKIP_GOLDEN_ON_WINDOWS = pytest.mark.skipif(
    WINDOWS, reason="goldens generated on Linux freetype; Windows produces slightly different pixels"
)

MOSAIC_W = KEY_SIZE * MK2_COLS + (MK2_COLS - 1) * 8
MOSAIC_H = KEY_SIZE * MK2_ROWS + (MK2_ROWS - 1) * 8


def _assert_matches_golden(img: Image.Image, name: str) -> None:
    target = GOLDENS / name
    if REGEN or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target)
        if not REGEN:
            pytest.fail(f"Golden {target} created (was missing). Re-run tests to verify.")
        return
    expected = Image.open(target).convert("RGB")
    diff = ImageChops.difference(img.convert("RGB"), expected)
    assert diff.getbbox() is None, f"image does not match golden {target}"


def _key(icon: IconSpec) -> KeyConfig:
    return KeyConfig(icon=icon, action=ShellAction(type="shell", cmd="true"))


@SKIP_GOLDEN_ON_WINDOWS
def test_text_only_blue_bg():
    k = _key(IconSpec(text="Tests", bg="#1e88e5"))
    img = render_key(k, state="idle")
    assert img.size == (KEY_SIZE, KEY_SIZE)
    assert img.mode == "RGB"
    _assert_matches_golden(img, "text_only_blue.png")


@SKIP_GOLDEN_ON_WINDOWS
def test_text_with_emoji():
    k = _key(IconSpec(text="Tests", emoji="🧪", bg="#1e88e5"))
    img = render_key(k, state="idle")
    _assert_matches_golden(img, "text_emoji_blue.png")


@SKIP_GOLDEN_ON_WINDOWS
def test_image_background_centered_and_scaled():
    img_path = Path(__file__).parent.parent / "fixtures" / "images" / "test-icon.png"
    k = _key(IconSpec(image=str(img_path), bg="#222222"))
    img = render_key(k, state="idle")
    _assert_matches_golden(img, "image_background.png")


@SKIP_GOLDEN_ON_WINDOWS
def test_state_active_uses_bg_active():
    k = _key(IconSpec(text="REC", bg_idle="#424242", bg_active="#d32f2f"))
    img = render_key(k, state="active")
    _assert_matches_golden(img, "state_active.png")


@SKIP_GOLDEN_ON_WINDOWS
def test_state_pressed_falls_back_to_idle_when_unspecified():
    k = _key(IconSpec(text="Build", bg="#43a047"))
    img = render_key(k, state="pressed")
    _assert_matches_golden(img, "state_pressed.png")


@SKIP_GOLDEN_ON_WINDOWS
def test_state_error_uses_default_red_when_unspecified():
    k = _key(IconSpec(text="Err", bg="#1e88e5"))
    img = render_key(k, state="error")
    _assert_matches_golden(img, "state_error.png")


@SKIP_GOLDEN_ON_WINDOWS
def test_state_disconnected_uses_default_gray():
    k = _key(IconSpec(text="Off", bg="#1e88e5"))
    img = render_key(k, state="disconnected")
    _assert_matches_golden(img, "state_disconnected.png")


def test_render_mosaic_dimensions():
    cfg = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "comprehensive.yaml")
    page = cfg.profiles["coding"].pages["home"]
    img = render_mosaic(page)
    assert img.size == (MOSAIC_W, MOSAIC_H)
    assert img.mode == "RGB"


def test_render_mosaic_empty_keys_are_blank():
    cfg = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "minimal.yaml")
    page = cfg.profiles["coding"].pages["home"]
    img = render_mosaic(page)
    # All keys are unconfigured → solid black mosaic
    assert img.getpixel((0, 0)) == (0, 0, 0)
    assert img.getpixel((MOSAIC_W - 1, MOSAIC_H - 1)) == (0, 0, 0)
