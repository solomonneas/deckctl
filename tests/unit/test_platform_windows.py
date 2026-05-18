"""Tests for the Windows platform shim's pure-Python lookup tables.

The pywin32 imports in `_vk_for` are inside the function body, so we can
exercise the table-driven dispatch (modifiers, special keys, single chars)
without pywin32 being installed - we only need to patch the win32api
single-char fallback path.

Runs on Linux CI; gives us coverage of the Windows special-key support
without a Windows VM.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def test_vk_for_resolves_named_special_keys():
    from deckctl.platform._windows import _vk_for
    assert _vk_for("Return") == 0x0D
    assert _vk_for("enter") == 0x0D
    assert _vk_for("Tab") == 0x09
    assert _vk_for("Escape") == 0x1B
    assert _vk_for("Up") == 0x26
    assert _vk_for("Down") == 0x28
    assert _vk_for("Left") == 0x25
    assert _vk_for("Right") == 0x27
    assert _vk_for("F1") == 0x70
    assert _vk_for("f12") == 0x7B
    assert _vk_for("apostrophe") == 0xDE


def test_vk_for_resolves_modifier_names():
    from deckctl.platform._windows import _vk_for
    assert _vk_for("ctrl") == 0x11
    assert _vk_for("CTRL") == 0x11
    assert _vk_for("shift") == 0x10
    assert _vk_for("alt") == 0x12
    assert _vk_for("win") == 0x5B
    assert _vk_for("cmd") == 0x5B


def test_vk_for_unknown_multichar_token_raises():
    from deckctl.platform._windows import _vk_for
    with pytest.raises(ValueError, match="unrecognized chord token"):
        _vk_for("not-a-known-key")


def test_vk_for_single_char_falls_back_to_vkkeyscan():
    """Single-character tokens dispatch to win32api.VkKeyScan."""
    # Build a fake win32api module so _vk_for's `import win32api` works on
    # Linux. The fake just returns a known VK value for 'a' (0x41) so we
    # can assert the codepath ran.
    fake_win32api = type(sys)("win32api")
    fake_win32api.VkKeyScan = lambda ch: 0x41  # 'A' / 0x41 in low byte
    with patch.dict(sys.modules, {"win32api": fake_win32api}):
        from deckctl.platform._windows import _vk_for
        assert _vk_for("a") == 0x41


def test_auto_key_chord_return_resolves():
    """The AUTO key in every preset uses key.chord: Return. Confirm it resolves."""
    from deckctl.platform._windows import _vk_for
    assert _vk_for("Return") == 0x0D


def test_terminal_page_chord_tokens_all_resolve():
    """coding preset terminal page uses ctrl+b prefix + named keys.

    Only exercises the named-key paths here; single-char leaves like 'b'/'z'/'d'
    fall through to win32api and are covered separately by
    test_vk_for_single_char_falls_back_to_vkkeyscan.
    """
    from deckctl.platform._windows import _vk_for
    for token in ["ctrl", "shift", "Up", "Down", "Left", "Right", "apostrophe"]:
        _vk_for(token)  # raises if unknown
