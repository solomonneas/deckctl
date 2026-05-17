from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import KeyChordAction, KeyTextAction


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...

    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")


def test_key_chord_calls_platform_send_chord():
    action = KeyChordAction(type="key.chord", keys="ctrl+shift+t")
    with patch("sdac.actions.keys.send_chord") as f:
        get_handler("key.chord").execute(action, _NullCtx())
    f.assert_called_once_with("ctrl+shift+t")


def test_key_text_calls_platform_type_text():
    action = KeyTextAction(type="key.text", text="console.log()")
    with patch("sdac.actions.keys.type_text") as f:
        get_handler("key.text").execute(action, _NullCtx())
    f.assert_called_once_with("console.log()")
