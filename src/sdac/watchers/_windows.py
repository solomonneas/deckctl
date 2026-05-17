"""Windows active-window watcher.

Polls GetForegroundWindow + GetWindowThreadProcessId every 250ms via pywin32.
Untested on Linux dev - verified on real Windows by running `sdac daemon`.

Imports `win32gui` / `psutil` are lazy (inside `_run`) so this module loads
cleanly on Linux (where pywin32 isn't installed).
"""

from __future__ import annotations

import logging
import os
import threading

from sdac.watchers.base import ActiveWindow, WatcherCallback

log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 0.25


class WindowsForegroundWatcher:
    """Polling watcher using win32 GetForegroundWindow."""

    def __init__(self) -> None:
        self._cb: WatcherCallback | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: ActiveWindow | None = None

    def start(self, on_change: WatcherCallback) -> None:
        if self._thread is not None:
            return
        self._cb = on_change
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sdac-watcher-win", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        # Imports inside _run so this module imports on non-Windows.
        import psutil  # type: ignore[import-untyped]
        import win32gui  # type: ignore[import-untyped]
        import win32process  # type: ignore[import-untyped]

        while not self._stop.is_set():
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid:
                        try:
                            proc = psutil.Process(pid)
                            name = os.path.basename(proc.exe()).lower()
                            aw = ActiveWindow(app_name=name)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            aw = ActiveWindow()
                        if aw != self._last:
                            self._last = aw
                            if self._cb is not None:
                                try:
                                    self._cb(aw)
                                except Exception:
                                    log.exception("active-window callback failed")
            except Exception:
                log.exception("win32 watcher poll error (continuing)")
            self._stop.wait(POLL_INTERVAL_SEC)
