"""Linux X11 active-window watcher.

Polls `_NET_ACTIVE_WINDOW` every 250ms via python-xlib. Fires the callback
when the focused window changes. Wayland is out of scope - the daemon will
fall back to NullWatcher if the X server can't be opened.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any

from Xlib import X  # type: ignore[import-untyped]
from Xlib import display as xdisplay
from Xlib import error as xerror

from deckctl.watchers.base import ActiveWindow, WatcherCallback

log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 0.25
POLL_ERROR_LOG_INTERVAL_SEC = 60.0


def _wm_class_for_window(window: Any) -> ActiveWindow:
    """Read WM_CLASS for a window and return an ActiveWindow.

    X11's WM_CLASS is a tuple of (instance_name, class_name); we prefer the
    class name. Returns ActiveWindow(app_class=None) when both are missing
    or on any X error.
    """
    try:
        wm = window.get_wm_class()
    except Exception:
        return ActiveWindow()
    if not wm:
        return ActiveWindow()
    chosen = wm[1] if len(wm) >= 2 else wm[0]
    if not chosen:
        return ActiveWindow()
    return ActiveWindow(app_class=str(chosen).lower())


class LinuxX11Watcher:
    """Polling watcher backed by python-xlib."""

    def __init__(self) -> None:
        self._display: Any = None
        self._cb: WatcherCallback | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: ActiveWindow | None = None

    def start(self, on_change: WatcherCallback) -> None:
        if self._thread is not None:
            if self._thread.is_alive():
                return
            self._thread = None
        self._cb = on_change
        self._stop.clear()
        try:
            self._display = xdisplay.Display()
        except Exception as exc:
            log.warning("X11 display unavailable; active-window watcher disabled: %s", exc)
            self._stop.set()
            return
        self._thread = threading.Thread(target=self._run, name="deckctl-watcher-x11", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None
        self._close_display()

    def _close_display(self) -> None:
        if self._display is not None:
            with contextlib.suppress(Exception):
                self._display.close()
            self._display = None

    def _run(self) -> None:
        assert self._display is not None
        root = self._display.screen().root
        net_active = self._display.intern_atom("_NET_ACTIVE_WINDOW")
        next_error_log = 0.0
        try:
            while not self._stop.is_set():
                try:
                    prop = root.get_full_property(net_active, X.AnyPropertyType)
                    if prop is not None and prop.value:
                        win_id = int(prop.value[0])
                        if win_id:
                            win = self._display.create_resource_object("window", win_id)
                            aw = _wm_class_for_window(win)
                            if aw != self._last:
                                self._last = aw
                                if self._cb is not None:
                                    try:
                                        self._cb(aw)
                                    except Exception:
                                        log.exception("active-window callback failed")
                except xerror.ConnectionClosedError as exc:
                    log.warning("X11 display connection closed; active-window watcher stopped: %s", exc)
                    self._stop.set()
                    break
                except Exception:
                    now = time.monotonic()
                    if now >= next_error_log:
                        log.exception(
                            "X11 watcher poll error; suppressing repeats for %.0fs",
                            POLL_ERROR_LOG_INTERVAL_SEC,
                        )
                        next_error_log = now + POLL_ERROR_LOG_INTERVAL_SEC
                self._stop.wait(POLL_INTERVAL_SEC)
        finally:
            self._close_display()
