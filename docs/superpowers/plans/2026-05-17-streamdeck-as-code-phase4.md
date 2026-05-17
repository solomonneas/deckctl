# streamdeck-as-code Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the focused window changes, evaluate `profile_rules:` from the config and auto-switch the active profile if a rule matches. Implement Linux X11 (`_NET_ACTIVE_WINDOW`) and Windows (`GetForegroundWindow`) watchers, plus Windows implementations for the platform shim functions that were raising `NotImplementedError`.

**Architecture:** A `Watcher` Protocol exposes `start(on_change)` and `stop()`. Concrete implementations are per-OS. Linux uses `python-xlib` to read `_NET_ACTIVE_WINDOW` + `WM_CLASS` with a polling loop. Windows uses `pywin32` + `ctypes` for `GetForegroundWindow` + process-name lookup, also polling. Polling rate is 250ms on both. The daemon owns the watcher, registers a callback that scans `profile_rules` top-to-bottom and calls `switch_profile` on first match.

**Tech Stack:** Python 3.12, `python-xlib>=0.33` (Linux extras), `pywin32>=306` (Windows extras), `pytest` with platform-conditional tests. Windows daemon Task Scheduler install is deferred to Phase 4b.

---

## Scope

**In Phase 4:**
- `Watcher` protocol + Linux X11 + Windows pywin32 implementations.
- `ActiveWindow` dataclass with `app_class` (Linux WM_CLASS, lowercase second token) and `app_name` (Windows process basename).
- Daemon evaluates `profile_rules` on every window change, switches profile on first match.
- Mock `Watcher` for tests.
- Windows platform shim: real implementations for `send_chord`, `type_text`, `media_play/pause/next/prev`; `volume_*` remains `NotImplementedError` with a clear message ("pycaw not yet integrated — Phase 4b").

**Deferred (Phase 4b):**
- `sdac install-service` on Windows (Task Scheduler at logon).
- pycaw integration for Windows volume control.
- `sdac doctor` row for Windows-specific systemd/udev replacements.

**Deferred (Phase 5):**
- GitHub repo creation, ClawHub publish, release tagging.

## File Structure

```
streamdeck-as-code/
  pyproject.toml                    # Modify: add [optional-dependencies] linux/windows extras
  src/sdac/
    watchers/
      __init__.py                   # NEW: facade + protocol + ActiveWindow + factory
      base.py                       # NEW: Watcher Protocol + ActiveWindow dataclass
      mock.py                       # NEW: MockWatcher for tests
      _linux.py                     # NEW: X11 watcher via python-xlib
      _windows.py                   # NEW: pywin32 watcher
    daemon.py                       # Modify: integrate watcher + profile_rules evaluation
    platform/
      _windows.py                   # Modify: replace NotImplementedError stubs (keep volume_* stubs)
    cli.py                          # Modify: --watch flag on `daemon` to enable/disable auto-switch
  tests/
    unit/
      test_watcher_mock.py          # NEW: MockWatcher mechanics
      test_watcher_linux.py         # NEW: Linux watcher with mocked xlib
      test_daemon_autoswitch.py     # NEW: profile_rules evaluation
    fixtures/
      configs/
        autoswitch.yaml             # NEW: minimal config exercising profile_rules
README.md                           # Modify: status + auto-profile-switch section
docs/schema.md                      # Modify: brief note on Phase 4 active-window matchers
```

---

## Task 1: Add platform-marked dependencies + watchers package skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `src/sdac/watchers/__init__.py`
- Create: `src/sdac/watchers/base.py`

- [ ] **Step 1: Add platform-marked extras to `pyproject.toml`**

Locate the existing `[project.optional-dependencies]` block. The current `dev` extras stay as-is; ADD these `[project.optional-dependencies]` entries (alphabetical):

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "ruff>=0.4",
    "mypy>=1.10",
    "types-PyYAML",
]
linux = [
    'python-xlib>=0.33 ; sys_platform == "linux"',
]
windows = [
    'pywin32>=306 ; sys_platform == "win32"',
]
```

Also extend the base `dependencies` list to pull in the right extra automatically per OS. Add these two lines at the end of `dependencies`:

```toml
    'python-xlib>=0.33 ; sys_platform == "linux"',
    'pywin32>=306 ; sys_platform == "win32"',
```

(Yes, both the base deps and the optional extras list them. The base ensures pipx-installed users get them automatically; the named extras are for `pip install -e ".[linux]"` etc.)

- [ ] **Step 2: Reinstall and verify import**

```bash
cd ~/repos/streamdeck-as-code
. .venv/bin/activate
pip install -e ".[dev]"
python -c "import Xlib; print('xlib ok')"
```

Expected: `xlib ok`. On Windows, `import win32api` would replace this; we're on Linux so only python-xlib matters.

- [ ] **Step 3: Write `src/sdac/watchers/base.py`**

```python
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
    Both may be None on the inactive-OS path or when introspection failed.
    """

    app_class: str | None = None
    app_name: str | None = None


WatcherCallback = Callable[[ActiveWindow], None]


@runtime_checkable
class Watcher(Protocol):
    """Polling watcher that fires `on_change` when the focused window changes."""

    def start(self, on_change: WatcherCallback) -> None: ...

    def stop(self) -> None: ...
```

- [ ] **Step 4: Write `src/sdac/watchers/__init__.py`** (facade; concrete OS modules land in Tasks 2 + 3)

```python
"""Active-window watcher facade.

The factory `make_watcher()` returns the right implementation for this OS.
On Linux it requires X11 (Wayland is out of scope for Phase 4).
On other OSes it returns a NullWatcher that never fires — daemon still runs,
no profile auto-switching happens.
"""

from __future__ import annotations

import sys

from sdac.watchers.base import ActiveWindow, Watcher, WatcherCallback


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
            from sdac.watchers._linux import LinuxX11Watcher
            return LinuxX11Watcher()
        except Exception:
            return NullWatcher()
    if sys.platform.startswith("win"):
        try:
            from sdac.watchers._windows import WindowsForegroundWatcher
            return WindowsForegroundWatcher()
        except Exception:
            return NullWatcher()
    return NullWatcher()


__all__ = ["ActiveWindow", "NullWatcher", "Watcher", "WatcherCallback", "make_watcher"]
```

- [ ] **Step 5: Verify imports**

```bash
python -c "from sdac.watchers import make_watcher, ActiveWindow, Watcher, NullWatcher; print('ok')"
```

Expected: `ok`. (The factory will raise / return NullWatcher because `_linux.py` doesn't exist yet — that's expected via the try/except.)

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 142 tests passing.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/sdac/watchers/__init__.py src/sdac/watchers/base.py
git commit -m "feat(watchers): facade + protocol + ActiveWindow value type"
```

---

## Task 2: MockWatcher + tests

**Files:**
- Create: `src/sdac/watchers/mock.py`
- Create: `tests/unit/test_watcher_mock.py`

- [ ] **Step 1: Write the failing test — `tests/unit/test_watcher_mock.py`**

```python
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


def test_mock_watcher_start_without_callback_is_a_noop():
    """Calling inject() before start() should not raise."""
    w = MockWatcher()
    w.inject(ActiveWindow(app_class="code"))  # silently dropped
```

- [ ] **Step 2: Run failing**

```bash
. .venv/bin/activate
pytest tests/unit/test_watcher_mock.py -v
```

Expected: ImportError on `sdac.watchers.mock`.

- [ ] **Step 3: Write `src/sdac/watchers/mock.py`**

```python
"""In-memory active-window watcher for tests."""

from __future__ import annotations

from sdac.watchers.base import ActiveWindow, WatcherCallback


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_watcher_mock.py -v
```

Expected: 3 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 145 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/watchers/mock.py tests/unit/test_watcher_mock.py
git commit -m "feat(watchers): MockWatcher for tests"
```

---

## Task 3: Linux X11 active-window watcher

**Files:**
- Create: `src/sdac/watchers/_linux.py`
- Create: `tests/unit/test_watcher_linux.py`

- [ ] **Step 1: Write failing test — `tests/unit/test_watcher_linux.py`**

```python
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

WINDOWS = sys.platform.startswith("win")
pytestmark = pytest.mark.skipif(WINDOWS, reason="Linux X11 watcher")

from sdac.watchers._linux import _wm_class_for_window  # noqa: E402
from sdac.watchers.base import ActiveWindow  # noqa: E402


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


def test_linux_watcher_constructor_does_not_open_display():
    """Construction is cheap; .start() opens the X display."""
    from sdac.watchers._linux import LinuxX11Watcher
    w = LinuxX11Watcher()
    assert w._display is None
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_watcher_linux.py -v
```

Expected: ImportError on `sdac.watchers._linux`.

- [ ] **Step 3: Write `src/sdac/watchers/_linux.py`**

```python
"""Linux X11 active-window watcher.

Polls `_NET_ACTIVE_WINDOW` every 250ms via python-xlib. Fires the callback
when the focused window changes. Wayland is out of scope — the daemon will
fall back to NullWatcher if the X server can't be opened.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from Xlib import display as xdisplay  # type: ignore[import-untyped]
from Xlib import X  # type: ignore[import-untyped]

from sdac.watchers.base import ActiveWindow, WatcherCallback

log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 0.25


def _wm_class_for_window(window: Any) -> ActiveWindow:
    """Read WM_CLASS for a window and return an ActiveWindow.

    X11's WM_CLASS is a tuple of (instance_name, class_name); we prefer the
    class name. Returns ActiveWindow(app_class=None) when both are missing.
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
            return
        self._cb = on_change
        self._stop.clear()
        self._display = xdisplay.Display()
        self._thread = threading.Thread(target=self._run, name="sdac-watcher-x11", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None
        if self._display is not None:
            try:
                self._display.close()
            except Exception:
                pass
            self._display = None

    def _run(self) -> None:
        assert self._display is not None
        root = self._display.screen().root
        net_active = self._display.intern_atom("_NET_ACTIVE_WINDOW")
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
            except Exception:
                log.exception("X11 watcher poll error (continuing)")
            self._stop.wait(POLL_INTERVAL_SEC)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_watcher_linux.py -v
```

Expected: 4 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 149 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/watchers/_linux.py tests/unit/test_watcher_linux.py
git commit -m "feat(watchers): Linux X11 active-window watcher (_NET_ACTIVE_WINDOW poll)"
```

---

## Task 4: Windows active-window watcher (untested locally)

**Files:**
- Create: `src/sdac/watchers/_windows.py`

(No new unit tests — pywin32 isn't installed on the Linux dev box. Tests for this module will require running on Windows. The implementation is structured so it's correct-by-inspection; runtime verification happens when Solomon plugs the Deck into the Windows host and runs `sdac daemon --config ...`.)

- [ ] **Step 1: Write `src/sdac/watchers/_windows.py`**

```python
"""Windows active-window watcher.

Polls GetForegroundWindow + GetWindowThreadProcessId every 250ms via pywin32.
Untested on Linux dev — verified on real Windows by running `sdac daemon`.
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
        import win32gui  # type: ignore[import-untyped]
        import win32process  # type: ignore[import-untyped]
        import psutil  # type: ignore[import-untyped]

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
```

- [ ] **Step 2: Add `psutil` to the Windows extras + base deps**

`psutil` is the simplest way to map pid → executable basename on Windows. Add it to the windows extras in `pyproject.toml`:

```toml
windows = [
    'pywin32>=306 ; sys_platform == "win32"',
    'psutil>=5.9 ; sys_platform == "win32"',
]
```

And to the base dependencies list:

```toml
    'psutil>=5.9 ; sys_platform == "win32"',
```

- [ ] **Step 3: Verify the module imports cleanly on Linux (just the import; not the runtime)**

```bash
. .venv/bin/activate
python -c "import sdac.watchers._windows; print('ok')"
```

Expected: `ok`. (The actual `_run()` body has `import win32gui` inside it which would fail at runtime — but that runtime path is never invoked on Linux.)

- [ ] **Step 4: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 149 tests passing.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/sdac/watchers/_windows.py
git commit -m "feat(watchers): Windows GetForegroundWindow watcher (untested on Linux dev)"
```

---

## Task 5: Daemon `profile_rules` auto-switch

**Files:**
- Modify: `src/sdac/daemon.py`
- Create: `tests/fixtures/configs/autoswitch.yaml`
- Create: `tests/unit/test_daemon_autoswitch.py`

- [ ] **Step 1: Write `tests/fixtures/configs/autoswitch.yaml`**

```yaml
version: 1
default_profile: coding
profile_rules:
  - profile: streaming
    when:
      app_class: [obs]
      app_name:  [obs64.exe]
  - profile: browsing
    when:
      app_class: [chromium, firefox]
      app_name:  [chrome.exe, firefox.exe]

profiles:
  coding:
    default_page: home
    pages:
      home:
        keys: {}
  streaming:
    default_page: home
    pages:
      home:
        keys: {}
  browsing:
    default_page: home
    pages:
      home:
        keys: {}
```

- [ ] **Step 2: Write failing tests — `tests/unit/test_daemon_autoswitch.py`**

```python
from __future__ import annotations

from pathlib import Path

import sdac.actions  # noqa: F401
from sdac.daemon import Daemon
from sdac.device import MockDevice
from sdac.watchers import ActiveWindow
from sdac.watchers.mock import MockWatcher

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_on_active_window_matches_first_rule_and_switches_profile():
    device = MockDevice()
    watcher = MockWatcher()
    d = Daemon(
        device=device,
        config_path=FIXTURES / "autoswitch.yaml",
        watcher=watcher,
    )
    d.load()
    d.render_current_page()
    d.start_watching_windows()
    assert d.current_profile == "coding"
    watcher.inject(ActiveWindow(app_class="obs"))
    assert d.current_profile == "streaming"


def test_active_window_no_match_keeps_current_profile():
    device = MockDevice()
    watcher = MockWatcher()
    d = Daemon(
        device=device,
        config_path=FIXTURES / "autoswitch.yaml",
        watcher=watcher,
    )
    d.load()
    d.render_current_page()
    d.start_watching_windows()
    watcher.inject(ActiveWindow(app_class="vim"))
    assert d.current_profile == "coding"


def test_active_window_matches_app_name_on_windows_style():
    device = MockDevice()
    watcher = MockWatcher()
    d = Daemon(
        device=device,
        config_path=FIXTURES / "autoswitch.yaml",
        watcher=watcher,
    )
    d.load()
    d.render_current_page()
    d.start_watching_windows()
    watcher.inject(ActiveWindow(app_name="chrome.exe"))
    assert d.current_profile == "browsing"


def test_repeat_match_does_not_re_switch_profile():
    """No redundant render storm when the same window stays focused."""
    device = MockDevice()
    watcher = MockWatcher()
    d = Daemon(
        device=device,
        config_path=FIXTURES / "autoswitch.yaml",
        watcher=watcher,
    )
    d.load()
    d.render_current_page()
    d.start_watching_windows()
    watcher.inject(ActiveWindow(app_class="obs"))
    device.images_pushed.clear()
    watcher.inject(ActiveWindow(app_class="obs"))
    assert device.images_pushed == {}  # already on streaming, no re-render


def test_first_matching_rule_wins():
    """Order matters: first match in profile_rules wins, even if a later rule also matches."""
    device = MockDevice()
    watcher = MockWatcher()
    d = Daemon(
        device=device,
        config_path=FIXTURES / "autoswitch.yaml",
        watcher=watcher,
    )
    d.load()
    d.render_current_page()
    d.start_watching_windows()
    # An ActiveWindow that matches both "streaming" (app_class=obs) and would also match if
    # we contrived a rule lower down — verify by checking only streaming gets selected.
    watcher.inject(ActiveWindow(app_class="obs", app_name="firefox.exe"))
    assert d.current_profile == "streaming"
```

- [ ] **Step 3: Extend `Daemon` constructor to accept a watcher + add evaluation logic**

In `src/sdac/daemon.py`:

1. Add the import (alphabetical):

```python
from sdac.watchers import ActiveWindow, NullWatcher, Watcher, make_watcher
```

2. Update the constructor signature. Find the existing `__init__` and replace its first line:

```python
    def __init__(
        self,
        device: Device,
        config_path: str | Path,
        *,
        watcher: Watcher | None = None,
    ) -> None:
```

3. In the body of `__init__`, after the existing attributes, add:

```python
        self._watcher: Watcher = watcher if watcher is not None else NullWatcher()
```

4. Add this method (anywhere after `start_obs_clients` / `stop_obs_clients`):

```python
    def start_watching_windows(self) -> None:
        """Subscribe to the active-window watcher; switch profile on match."""
        self._watcher.start(self._on_active_window)

    def stop_watching_windows(self) -> None:
        self._watcher.stop()

    def _on_active_window(self, window: ActiveWindow) -> None:
        with self._lock:
            if self._config is None:
                return
            rules = list(self._config.profile_rules)
        for rule in rules:
            if self._rule_matches(rule, window):
                if rule.profile != self._current_profile:
                    self.switch_profile(rule.profile)
                return

    def _rule_matches(self, rule: "ProfileRule", window: ActiveWindow) -> bool:
        if window.app_class and window.app_class in rule.when.app_class:
            return True
        if window.app_name and window.app_name in rule.when.app_name:
            return True
        return False
```

(Add `ProfileRule` to the `from sdac.config import ...` line if it's not already imported.)

5. Update `run_forever` so it starts and stops the window watcher too. Find the `start_obs_clients()` line and add `self.start_watching_windows()` right after it. In the `finally` block, add `self.stop_watching_windows()` after `self.stop_obs_clients()`.

The final `run_forever` should look like:

```python
    def run_forever(self) -> None:
        stop = threading.Event()

        def handle(signum: int, frame: object) -> None:
            del frame
            log.info("received signal %d; stopping", signum)
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, handle)

        self.start_obs_clients()
        self.start_watching_windows()
        try:
            while not stop.is_set():
                stop.wait(timeout=1.0)
        finally:
            self.stop_obs_clients()
            self.stop_watching_windows()
            self.stop_watching()
            if self._device.is_open:
                self._device.close()
```

- [ ] **Step 4: Update `sdac.cli.daemon` to inject `make_watcher()` by default**

In `src/sdac/cli.py`, find the `daemon` command. Locate the line that constructs `Daemon`:

```python
    d = Daemon(device=device, config_path=config_path)
```

Replace with:

```python
    from sdac.watchers import make_watcher
    d = Daemon(device=device, config_path=config_path, watcher=make_watcher())
```

- [ ] **Step 5: Run failing tests**

```bash
. .venv/bin/activate
pytest tests/unit/test_daemon_autoswitch.py -v
```

Expected: failing (until daemon changes are in place).

- [ ] **Step 6: Run after implementation**

```bash
pytest tests/unit/test_daemon_autoswitch.py -v
```

Expected: 5 passing.

- [ ] **Step 7: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 154 tests passing.

- [ ] **Step 8: Commit**

```bash
git add src/sdac/daemon.py src/sdac/cli.py \
        tests/unit/test_daemon_autoswitch.py tests/fixtures/configs/autoswitch.yaml
git commit -m "feat(daemon): profile_rules auto-switch via active-window watcher"
```

---

## Task 6: Windows platform shim — keys + media (volume stays NotImplementedError)

**Files:**
- Modify: `src/sdac/platform/_windows.py`

(No new tests — pywin32 not on Linux dev. The code is correct-by-inspection.)

- [ ] **Step 1: Replace the body of `src/sdac/platform/_windows.py`**

```python
"""Windows implementations of platform-dependent action primitives.

`send_chord`, `type_text`, and the four `media_*` functions are implemented
via pywin32's keybd_event. `volume_*` remains NotImplementedError — Phase 4b
will wire pycaw or shell to nircmd.

Untested on the Linux dev machine; correctness will be verified when the
Stream Deck is plugged into the Windows host and a daemon is running.
"""

from __future__ import annotations

import subprocess
import webbrowser


# Windows virtual key codes for media keys (https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes)
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PREV_TRACK = 0xB1
_VK_MEDIA_STOP = 0xB2
_VK_MEDIA_PLAY_PAUSE = 0xB3

# Modifier virtual key codes (subset used by send_chord)
_VK_MODIFIERS = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
    "meta": 0x5B,
    "super": 0x5B,
    "cmd": 0x5B,
}
_KEYEVENTF_KEYUP = 0x0002


def _keybd_event(vk: int, up: bool = False) -> None:
    """Send a single key down or up via pywin32's keybd_event."""
    import win32api  # type: ignore[import-untyped]
    flags = _KEYEVENTF_KEYUP if up else 0
    win32api.keybd_event(vk, 0, flags, 0)


def _vk_for(token: str) -> int:
    """Resolve a chord token (a modifier name or single character) to a virtual key code."""
    import win32api  # type: ignore[import-untyped]
    token = token.lower()
    if token in _VK_MODIFIERS:
        return _VK_MODIFIERS[token]
    if len(token) == 1:
        # VkKeyScanW returns the VK code in the low byte and shift state in the high byte.
        vk = win32api.VkKeyScanW(token) & 0xFF
        return vk
    raise ValueError(f"unrecognized chord token: {token!r}")


def send_chord(keys: str) -> None:
    """Send a chord like 'ctrl+shift+t'."""
    tokens = [t.strip() for t in keys.split("+") if t.strip()]
    vks = [_vk_for(t) for t in tokens]
    for vk in vks:
        _keybd_event(vk, up=False)
    for vk in reversed(vks):
        _keybd_event(vk, up=True)


def type_text(text: str) -> None:
    """Type a literal string via win32 SendInput (one character at a time)."""
    import win32api  # type: ignore[import-untyped]
    for ch in text:
        vk_and_shift = win32api.VkKeyScanW(ch)
        vk = vk_and_shift & 0xFF
        shift = (vk_and_shift >> 8) & 0xFF
        if shift & 1:  # need shift held
            _keybd_event(_VK_MODIFIERS["shift"], up=False)
        _keybd_event(vk, up=False)
        _keybd_event(vk, up=True)
        if shift & 1:
            _keybd_event(_VK_MODIFIERS["shift"], up=True)


def _todo(name: str) -> None:
    raise NotImplementedError(
        f"platform function {name!r} not yet implemented on Windows "
        "(volume control needs pycaw; queued for Phase 4b)"
    )


def volume_up(step: int = 5) -> None:
    del step
    _todo("volume_up")


def volume_down(step: int = 5) -> None:
    del step
    _todo("volume_down")


def volume_mute() -> None:
    _todo("volume_mute")


def media_play() -> None:
    # Most apps treat MEDIA_PLAY_PAUSE as "play if paused"; the discrete media_play
    # signal also exists at 0xB3 (treat them the same for v1).
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=False)
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=True)


def media_pause() -> None:
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=False)
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=True)


def media_next() -> None:
    _keybd_event(_VK_MEDIA_NEXT_TRACK, up=False)
    _keybd_event(_VK_MEDIA_NEXT_TRACK, up=True)


def media_prev() -> None:
    _keybd_event(_VK_MEDIA_PREV_TRACK, up=False)
    _keybd_event(_VK_MEDIA_PREV_TRACK, up=True)


def open_url(url: str) -> None:
    webbrowser.open(url)


def open_app(path: str) -> None:
    """Launch a binary detached. On Windows we don't use start_new_session;
    `Popen` alone gives the child its own console + process group."""
    subprocess.Popen([path])
```

- [ ] **Step 2: Verify the module imports cleanly on Linux**

```bash
. .venv/bin/activate
python -c "import sdac.platform._windows; print('ok')"
```

Expected: `ok`. (Function calls would fail at runtime because pywin32 isn't installed on Linux — but the import path doesn't invoke them.)

- [ ] **Step 3: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 154 tests passing.

- [ ] **Step 4: Commit**

```bash
git add src/sdac/platform/_windows.py
git commit -m "feat(platform/windows): keys + media via keybd_event; volume_* still NotImplementedError (Phase 4b)"
```

---

## Task 7: README + schema docs

**Files:**
- Modify: `README.md`
- Modify: `docs/schema.md`

- [ ] **Step 1: Update the README status block**

Find `**Status:** Phase 3 (current). ...` and replace with:

```markdown
**Status:** Phase 4 (current). `sdac daemon` runs on Linux end-to-end including auto-profile-switching driven by the focused window (X11). Windows daemon code is in place (keys + media + active-window watcher) but the Task Scheduler install verb + Windows volume control are queued for Phase 4b. OBS execution + live indicators work as of Phase 3.
```

- [ ] **Step 2: Update the `## Capabilities` heading and bullets**

Replace with:

```markdown
## Capabilities (Phase 1 + 2a + 2b + 3 + 4)

- Validate a YAML config against the full v1 schema (Pydantic 2 discriminated union over 21 action types).
- Resolve `${ENV_VAR}` in any string field — keep passwords out of the YAML.
- Render every key in a profile/page as a single mosaic PNG (offline preview, no device required).
- Warn (or strict-reject with `--strict-perms`) when the config file is world-readable on POSIX.
- Run a daemon that owns a real Stream Deck MK.2 over USB and dispatches button presses to handlers.
- Hot-reload the config without restarting the daemon.
- Execute OBS actions over the LAN: scene switch, recording/streaming/replay/virtualcam toggle, audio mute.
- Live state indicators: keys bound to OBS recording/streaming/replay/scene/mute auto-update when OBS state changes.
- **Auto profile switching:** define `profile_rules:` matching `app_class` (Linux) or `app_name` (Windows); the daemon switches profiles when the focused window matches.
- Install as a systemd user unit with one command (`sdac install-service`). Daemon autostarts at login.
- `sdac doctor` reports on device, deps, service status, config, and OBS reachability — exits non-zero on any FAIL.
```

- [ ] **Step 3: Add a new auto-switch section to `README.md`**

After the existing `## OBS integration (Phase 3)` section, insert:

```markdown
## Auto profile switching (Phase 4)

Add `profile_rules:` to your config to switch profiles automatically when the focused application changes:

```yaml
profile_rules:
  - profile: streaming
    when:
      app_class: [obs]            # Linux WM_CLASS (lowercased)
      app_name:  [obs64.exe]      # Windows process basename (lowercased)
  - profile: coding
    when:
      app_class: [code, jetbrains-idea-ce, ghostty]
      app_name:  [code.exe, idea64.exe, windowsterminal.exe]
  - profile: browsing
    when:
      app_class: [chromium, firefox]
      app_name:  [chrome.exe, firefox.exe]

default_profile: coding
```

Rules are evaluated top-to-bottom; the first match wins. Linux uses X11's `_NET_ACTIVE_WINDOW` + `WM_CLASS`; Windows uses `GetForegroundWindow` + the process basename. Both poll every 250ms — fast enough to feel instant. Wayland is not supported in Phase 4 (the daemon falls back to "no auto-switch" if it can't open an X display).
```

- [ ] **Step 4: Update `docs/schema.md`**

Find the existing `profile_rules:` block in the top-level schema. After the existing line that begins with `profile_rules: ...`, append a sentence:

```markdown
**Phase 4 runtime note:** the daemon evaluates `profile_rules` top-to-bottom on every focused-window change. Linux X11 reads `WM_CLASS` (lowercased), Windows reads the process basename (lowercased). First match wins; no match keeps the current profile. Wayland is unsupported.
```

- [ ] **Step 5: Full check**

```bash
. .venv/bin/activate
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 154 tests passing.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/schema.md
git commit -m "docs: Phase 4 — auto profile switching section + status update"
```

### Step 7: Report Phase 4 commit chain

```bash
git log --oneline d41902f..HEAD
```

---

## Done criteria for Phase 4

1. Linux X11 active-window watcher polls `_NET_ACTIVE_WINDOW`, emits `ActiveWindow(app_class=...)` on focus change. Tested with mocked python-xlib.
2. Windows watcher code is in place using pywin32 + psutil; imports cleanly on Linux; not runtime-tested.
3. Daemon evaluates `profile_rules` on watcher callbacks; first match wins; same-profile injection is a no-op.
4. Windows platform shim implements `send_chord`, `type_text`, and the four `media_*` keys via `keybd_event`. `volume_*` still raises `NotImplementedError` with a Phase 4b message.
5. Tests: 154+ passing. ruff + mypy clean.

## Deferred to Phase 4b

- `sdac install-service` Windows path (Task Scheduler at logon registration).
- `volume_*` on Windows (pycaw integration).
- Doctor row variants for non-systemd hosts.

## Deferred to Phase 5

- GitHub repo creation + push.
- ClawHub publish.
- Release tagging.
