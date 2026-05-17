"""Renderer tests. Uses golden images.

Regenerate goldens by running:
    SDAC_REGEN=1 pytest tests/unit/test_render.py
Review the resulting PNGs in tests/fixtures/goldens/ before committing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from sdac.config import IconSpec, KeyConfig, ShellAction
from sdac.render import KEY_SIZE, render_key

GOLDENS = Path(__file__).parent.parent / "fixtures" / "goldens"
REGEN = os.environ.get("SDAC_REGEN") == "1"


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


def test_text_only_blue_bg():
    k = _key(IconSpec(text="Tests", bg="#1e88e5"))
    img = render_key(k, state="idle")
    assert img.size == (KEY_SIZE, KEY_SIZE)
    assert img.mode == "RGB"
    _assert_matches_golden(img, "text_only_blue.png")


def test_text_with_emoji():
    k = _key(IconSpec(text="Tests", emoji="🧪", bg="#1e88e5"))
    img = render_key(k, state="idle")
    _assert_matches_golden(img, "text_emoji_blue.png")


def test_image_background_centered_and_scaled():
    img_path = Path(__file__).parent.parent / "fixtures" / "images" / "test-icon.png"
    k = _key(IconSpec(image=str(img_path), bg="#222222"))
    img = render_key(k, state="idle")
    _assert_matches_golden(img, "image_background.png")
