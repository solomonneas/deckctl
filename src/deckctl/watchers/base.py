"""Active-window watcher protocol + value type."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ActiveWindow:
    """Identity of the currently-focused window.

    `app_class` is the Linux `WM_CLASS` (the second component, lowercased).
    `app_name` is the Windows process basename (e.g. "obs64.exe", lowercased).
    Both may be None when introspection failed.
    """

    app_class: str | None = None
    app_name: str | None = None


WatcherCallback = Callable[[ActiveWindow], None]


@runtime_checkable
class Watcher(Protocol):
    """Polling watcher that fires `on_change` when the focused window changes."""

    def start(self, on_change: WatcherCallback) -> None: ...

    def stop(self) -> None: ...
