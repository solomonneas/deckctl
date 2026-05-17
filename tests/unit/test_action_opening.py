from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import OpenAppAction, OpenUrlAction


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...

    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")


def test_open_url_calls_platform_open_url():
    action = OpenUrlAction(type="open.url", url="https://example.com")
    with patch("sdac.actions.opening.open_url") as f:
        get_handler("open.url").execute(action, _NullCtx())
    f.assert_called_once_with("https://example.com")


def test_open_app_with_path_calls_open_app():
    action = OpenAppAction(type="open.app", path="/usr/bin/code")
    with patch("sdac.actions.opening.open_app") as f:
        get_handler("open.app").execute(action, _NullCtx())
    f.assert_called_once_with("/usr/bin/code")


def test_open_app_with_name_falls_back_to_xdg_open():
    action = OpenAppAction(type="open.app", name="firefox")
    with patch("subprocess.Popen") as popen:
        get_handler("open.app").execute(action, _NullCtx())
    args, kwargs = popen.call_args
    assert args[0] == ["xdg-open", "firefox"]
    assert kwargs.get("start_new_session") is True
