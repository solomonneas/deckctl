from __future__ import annotations

from sdac.watchers import ActiveWindow
from sdac.watchers.mock import MockWatcher


def test_mock_watcher_fires_on_inject():
    w = MockWatcher()
    received: list[ActiveWindow] = []
    w.start(lambda aw: received.append(aw))
    w.inject(ActiveWindow(app_class="code", app_name="Code.exe"))
    w.inject(ActiveWindow(app_class="firefox", app_name="firefox.exe"))
    assert len(received) == 2
    assert received[0].app_class == "code"
    assert received[1].app_class == "firefox"


def test_mock_watcher_stop_disables_inject():
    w = MockWatcher()
    received: list[ActiveWindow] = []
    w.start(lambda aw: received.append(aw))
    w.stop()
    w.inject(ActiveWindow(app_class="code"))
    assert received == []


def test_mock_watcher_inject_before_start_is_silently_dropped():
    w = MockWatcher()
    w.inject(ActiveWindow(app_class="code"))  # no exception
