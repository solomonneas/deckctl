"""Active-window watcher facade.

`make_watcher()` returns the right implementation for this OS. On Linux it
requires X11 (Wayland is out of scope). On other OSes or when the platform
backend can't initialize, it returns a NullWatcher that never fires -
daemon still runs, no profile auto-switching happens.
"""

from __future__ import annotations

import sys
from typing import cast

from deckctl.watchers.base import ActiveWindow, Watcher, WatcherCallback


class NullWatcher:
    """A `Watcher` that never fires. Used when no real backend is available."""

    def start(self, on_change: WatcherCallback) -> None:
        del on_change

    def stop(self) -> None:
        pass


def make_watcher() -> Watcher:
    """Return the active-window watcher implementation for this OS."""
    if sys.platform.startswith("linux"):
        try:
            from deckctl.watchers._linux import LinuxX11Watcher

            return cast(Watcher, LinuxX11Watcher())
        except Exception:
            return NullWatcher()
    if sys.platform.startswith("win"):
        try:
            from deckctl.watchers._windows import WindowsForegroundWatcher

            return cast(Watcher, WindowsForegroundWatcher())
        except Exception:
            return NullWatcher()
    return NullWatcher()


__all__ = ["ActiveWindow", "NullWatcher", "Watcher", "WatcherCallback", "make_watcher"]
