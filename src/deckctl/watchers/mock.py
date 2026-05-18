"""In-memory active-window watcher for tests."""

from __future__ import annotations

from deckctl.watchers.base import ActiveWindow, WatcherCallback


class MockWatcher:
    """A `Watcher` implementation that lets tests inject ActiveWindow events."""

    def __init__(self) -> None:
        self._cb: WatcherCallback | None = None

    def start(self, on_change: WatcherCallback) -> None:
        self._cb = on_change

    def stop(self) -> None:
        self._cb = None

    def inject(self, window: ActiveWindow) -> None:
        """Synchronously fire the registered callback (or no-op if not started)."""
        if self._cb is not None:
            self._cb(window)
