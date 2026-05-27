from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from Xlib import error as xerror

WINDOWS = sys.platform.startswith("win")
if WINDOWS:
    pytest.skip("Linux X11 watcher", allow_module_level=True)

from deckctl.watchers._linux import LinuxX11Watcher, _wm_class_for_window  # noqa: E402
from deckctl.watchers.base import ActiveWindow  # noqa: E402


def test_wm_class_extracts_second_component_lowercased():
    """X11's WM_CLASS returns (instance, class); we use class lowercased."""
    fake_window = MagicMock()
    fake_window.get_wm_class.return_value = ("code", "Code")
    aw = _wm_class_for_window(fake_window)
    assert aw == ActiveWindow(app_class="code")


def test_wm_class_falls_back_to_first_when_second_missing():
    fake_window = MagicMock()
    fake_window.get_wm_class.return_value = ("firefox",)
    aw = _wm_class_for_window(fake_window)
    assert aw == ActiveWindow(app_class="firefox")


def test_wm_class_returns_empty_when_none():
    fake_window = MagicMock()
    fake_window.get_wm_class.return_value = None
    aw = _wm_class_for_window(fake_window)
    assert aw == ActiveWindow(app_class=None)


def test_wm_class_handles_exceptions_gracefully():
    fake_window = MagicMock()
    fake_window.get_wm_class.side_effect = RuntimeError("X error")
    aw = _wm_class_for_window(fake_window)
    assert aw == ActiveWindow(app_class=None)


def test_linux_watcher_constructor_does_not_open_display():
    """Construction is cheap; .start() opens the X display."""
    w = LinuxX11Watcher()
    assert w._display is None


def test_linux_watcher_start_disables_when_display_unavailable(monkeypatch, caplog):
    def raise_display() -> object:
        raise RuntimeError("no display")

    monkeypatch.setattr("deckctl.watchers._linux.xdisplay.Display", raise_display)
    w = LinuxX11Watcher()

    w.start(lambda _window: None)

    assert w._thread is None
    assert w._display is None
    assert w._stop.is_set()
    assert "X11 display unavailable" in caplog.text


def test_linux_watcher_stops_when_display_connection_closes(caplog):
    """A dead X socket should stop the watcher, not spam syslog forever."""

    class FakeRoot:
        def get_full_property(self, _atom: object, _property_type: object) -> object:
            raise xerror.ConnectionClosedError("test display")

    class FakeScreen:
        root = FakeRoot()

    class FakeDisplay:
        def __init__(self) -> None:
            self.closed = False

        def screen(self) -> FakeScreen:
            return FakeScreen()

        def intern_atom(self, _name: str) -> int:
            return 1

        def close(self) -> None:
            self.closed = True

    w = LinuxX11Watcher()
    fake_display = FakeDisplay()
    w._display = fake_display

    w._run()

    assert w._stop.is_set()
    assert fake_display.closed is True
    assert w._display is None
    assert "X11 display connection closed" in caplog.text
