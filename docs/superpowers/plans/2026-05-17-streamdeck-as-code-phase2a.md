# streamdeck-as-code Phase 2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a Linux daemon that owns a Stream Deck MK.2 over USB, renders the active profile/page from the YAML config, dispatches button presses to built-in action handlers (shell, keys, open, system audio, media, navigation, compound), and hot-reloads the config on file change.

**Architecture:** Synchronous threaded daemon. `sdac.device` wraps `python-elgato-streamdeck`; a parallel `MockDevice` powers tests with zero hardware. `sdac.actions` is a registry of handler classes that receive a typed action + a `DaemonContext` for navigation calls. `sdac.platform._linux` shells out to `xdotool`, `pactl`, and `playerctl` for keystroke/audio/media actions - `_windows` exists as a stub raising `NotImplementedError` so the package imports cleanly on Windows (Phase 4 fills it in). `watchdog` watches the config file; valid reloads diff against the previous render set and only re-push changed keys. Daemon survives device unplug by polling for re-enumeration with exponential backoff.

**Tech Stack:** Python 3.12, `streamdeck>=0.9` (python-elgato-streamdeck), `watchdog>=4.0`, system packages `xdotool`, `pactl` (PulseAudio/PipeWire), `playerctl`. Tests use `pytest`, no real hardware required.

---

## Scope

**In Phase 2a:**
- USB HID I/O for Stream Deck MK.2 via `streamdeck` library
- Daemon lifecycle: open → render → dispatch → close
- Built-in action handlers: shell, key.chord, key.text, open.url, open.app, system.volume.up/down/mute, media.play/pause/next/prev, page.go, profile.switch, compound
- Hot reload on config edit
- Device hotplug resilience (poll + reconnect)
- `sdac daemon` CLI verb (foreground; backgrounding is Phase 2b's systemd unit's job)
- Mock device fixture for tests
- End-to-end integration test with MockDevice

**Deferred (Phase 2b):** systemd unit install, udev rule install, `sdac doctor`, README install instructions for service setup.

**Deferred (Phase 3):** OBS action execution (`obs.*` types validate but raise `NotImplementedError` at dispatch - schema is already valid), live state indicators, async websocket loop.

**Deferred (Phase 4):** Windows daemon, active-window watcher, Wayland.

## File Structure

```
streamdeck-as-code/
  pyproject.toml                                # Modify: add streamdeck + watchdog deps
  src/sdac/
    cli.py                                      # Modify: add `daemon` verb
    daemon.py                                   # NEW: orchestrator
    device/
      __init__.py                               # NEW: re-exports
      base.py                                   # NEW: Device protocol, KeyEvent type
      mock.py                                   # NEW: MockDevice (for tests)
      streamdeck.py                             # NEW: real StreamDeckDevice
    platform/
      __init__.py                               # NEW: re-exports
      _linux.py                                 # NEW: xdotool/pactl/playerctl shell-outs
      _windows.py                               # NEW: stubs raising NotImplementedError
    actions/
      __init__.py                               # NEW: HANDLERS registry, get_handler()
      base.py                                   # NEW: ActionHandler protocol, DaemonContext protocol
      shell.py                                  # NEW
      keys.py                                   # NEW: key.chord + key.text
      opening.py                                # NEW: open.url + open.app
      system_audio.py                           # NEW: volume + media
      compound.py                               # NEW
      navigation.py                             # NEW: page.go + profile.switch
      obs.py                                    # NEW: stub handlers that raise; Phase 3 fills
  tests/
    unit/
      test_device_mock.py                       # NEW
      test_actions_registry.py                  # NEW
      test_action_shell.py                      # NEW
      test_action_keys.py                       # NEW
      test_action_opening.py                    # NEW
      test_action_system_audio.py               # NEW
      test_action_compound.py                   # NEW
      test_action_navigation.py                 # NEW
      test_platform_linux.py                    # NEW
      test_daemon.py                            # NEW
    integration/
      __init__.py                               # NEW
      test_daemon_e2e.py                        # NEW: full lifecycle on MockDevice
    fixtures/
      configs/
        daemon_smoke.yaml                       # NEW: minimal exercise of every handler
```

**Boundary contracts:**
- `device.base.Device` is the only HID-touching protocol; `daemon.py` never imports the `streamdeck` library directly.
- `actions.base.DaemonContext` is the only way handlers reach the daemon. Handlers don't import `daemon.py`.
- `platform._linux` is the only module that calls `subprocess` for keystrokes / audio / media. Actions call platform functions, never `subprocess` directly.

---

## Task 1: Add runtime dependencies + platform docs note

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md` (one paragraph about Linux system deps)

- [ ] **Step 1: Add `streamdeck` and `watchdog` to `[project] dependencies` in `pyproject.toml`**

Locate the `dependencies = [...]` block and append two entries so it reads:

```toml
dependencies = [
    "click>=8.1",
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "pillow>=10.2",
    "pilmoji>=2.0",
    "streamdeck>=0.9",
    "watchdog>=4.0",
]
```

- [ ] **Step 2: Add a "Linux runtime dependencies" subsection to `README.md`**

Append to the README under the `## Install` section:

```markdown
### Linux runtime dependencies

Phase 2+ actions shell out to a few system utilities. On Ubuntu / Debian:

```bash
sudo apt install -y xdotool playerctl
# pactl ships with pulseaudio-utils on PulseAudio or pipewire-pulse on PipeWire
```

`xdotool` is required for `key.chord` and `key.text` actions. `pactl` is required for `system.volume.*`. `playerctl` is required for `media.*`. The daemon does not require any of them at startup, only at the moment an action that uses them is dispatched.
```

- [ ] **Step 3: Reinstall the editable package so new deps land**

```bash
cd ~/repos/streamdeck-as-code
. .venv/bin/activate
pip install -e ".[dev]"
python -c "import StreamDeck.DeviceManager, watchdog; print('ok')"
```

Expected: `ok`. The `streamdeck` PyPI package imports as `StreamDeck` (capitalized) - that's correct, not a typo.

- [ ] **Step 4: Full check still passes**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 29 tests passing (Phase 1 tests untouched).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md
git commit -m "deps: add streamdeck + watchdog for Phase 2a daemon"
```

---

## Task 2: Device abstraction (Protocol) + MockDevice

**Files:**
- Create: `src/sdac/device/__init__.py`
- Create: `src/sdac/device/base.py`
- Create: `src/sdac/device/mock.py`
- Create: `tests/unit/test_device_mock.py`

- [ ] **Step 1: Write the failing test - `tests/unit/test_device_mock.py`**

```python
from __future__ import annotations

from PIL import Image

from sdac.device import MockDevice
from sdac.device.base import KeyEvent


def test_mock_device_open_close():
    d = MockDevice()
    assert not d.is_open
    d.open()
    assert d.is_open
    d.close()
    assert not d.is_open


def test_mock_device_key_count_defaults_to_15():
    assert MockDevice().key_count == 15


def test_mock_device_records_pushed_images():
    d = MockDevice()
    d.open()
    img = Image.new("RGB", (72, 72), "#ff0000")
    d.set_key_image(0, img)
    assert d.images_pushed[0].getpixel((0, 0)) == (255, 0, 0)


def test_mock_device_callback_fires_on_inject_press():
    d = MockDevice()
    d.open()
    events: list[KeyEvent] = []
    d.register_key_callback(lambda e: events.append(e))
    d.inject_press(3)
    assert events == [KeyEvent(key=3, pressed=True), KeyEvent(key=3, pressed=False)]


def test_mock_device_set_key_image_rejects_out_of_range():
    d = MockDevice()
    d.open()
    img = Image.new("RGB", (72, 72))
    try:
        d.set_key_image(99, img)
    except IndexError:
        return
    raise AssertionError("expected IndexError for key 99")
```

- [ ] **Step 2: Run failing tests**

```bash
. .venv/bin/activate
pytest tests/unit/test_device_mock.py -v
```

Expected: ImportError (modules not created).

- [ ] **Step 3: Write `src/sdac/device/base.py`**

```python
"""Device abstraction. The daemon talks to this protocol; concrete devices
(StreamDeckDevice, MockDevice) implement it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PIL import Image


@dataclass(frozen=True)
class KeyEvent:
    """Press or release of a physical key."""

    key: int
    pressed: bool


KeyCallback = Callable[[KeyEvent], None]


@runtime_checkable
class Device(Protocol):
    """The minimum surface the daemon needs from a Stream Deck-like device."""

    @property
    def is_open(self) -> bool: ...

    @property
    def key_count(self) -> int: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def set_key_image(self, key: int, image: Image.Image) -> None: ...

    def register_key_callback(self, callback: KeyCallback) -> None: ...
```

- [ ] **Step 4: Write `src/sdac/device/mock.py`**

```python
"""In-memory device used by the daemon test suite. No HID, no threads."""

from __future__ import annotations

from PIL import Image

from sdac.device.base import KeyCallback, KeyEvent


class MockDevice:
    """A `Device` implementation that records pushed images and lets tests
    inject button presses."""

    def __init__(self, key_count: int = 15) -> None:
        self._key_count = key_count
        self._open = False
        self._callbacks: list[KeyCallback] = []
        self.images_pushed: dict[int, Image.Image] = {}

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def key_count(self) -> int:
        return self._key_count

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def set_key_image(self, key: int, image: Image.Image) -> None:
        if not 0 <= key < self._key_count:
            raise IndexError(f"key {key} out of range 0..{self._key_count - 1}")
        self.images_pushed[key] = image.copy()

    def register_key_callback(self, callback: KeyCallback) -> None:
        self._callbacks.append(callback)

    def inject_press(self, key: int) -> None:
        """Fire press + release for `key`. Tests use this to simulate a button push."""
        for cb in list(self._callbacks):
            cb(KeyEvent(key=key, pressed=True))
        for cb in list(self._callbacks):
            cb(KeyEvent(key=key, pressed=False))
```

- [ ] **Step 5: Write `src/sdac/device/__init__.py`**

```python
"""Device abstraction + concrete implementations."""

from sdac.device.base import Device, KeyCallback, KeyEvent
from sdac.device.mock import MockDevice

__all__ = ["Device", "KeyCallback", "KeyEvent", "MockDevice"]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_device_mock.py -v
```

Expected: 5 passing.

- [ ] **Step 7: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 34 tests passing.

- [ ] **Step 8: Commit**

```bash
git add src/sdac/device/ tests/unit/test_device_mock.py
git commit -m "feat(device): Device protocol + MockDevice for tests"
```

---

## Task 3: Real StreamDeckDevice wrapper

**Files:**
- Create: `src/sdac/device/streamdeck.py`
- Modify: `src/sdac/device/__init__.py`

(No new tests here - the real wrapper requires real hardware to exercise. We trust `python-elgato-streamdeck`'s own tests and verify by manual smoke in Task 16. The wrapper's only responsibilities are translating to/from our types.)

- [ ] **Step 1: Write `src/sdac/device/streamdeck.py`**

```python
"""Real Stream Deck wrapper around the upstream `streamdeck` library.

The daemon never imports `streamdeck.*` directly - all HID code lives here.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

from sdac.device.base import KeyCallback, KeyEvent
from sdac.errors import SdacError


class DeviceNotFoundError(SdacError):
    """Raised when no Stream Deck device is enumerated on the bus."""


class StreamDeckDevice:
    """Adapter from a `streamdeck.StreamDeck` instance to our `Device` protocol."""

    def __init__(self, deck: Any) -> None:
        # `deck` is a `StreamDeck.Devices.StreamDeck.StreamDeck` subclass; we
        # treat it as `Any` because that library does not ship type stubs.
        self._deck = deck
        self._callbacks: list[KeyCallback] = []
        self._open = False

    @classmethod
    def enumerate_first(cls) -> StreamDeckDevice:
        """Return the first Stream Deck found, or raise DeviceNotFoundError."""
        decks = DeviceManager().enumerate()
        if not decks:
            raise DeviceNotFoundError(
                "no Stream Deck device found (check USB connection + udev permissions)"
            )
        return cls(decks[0])

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def key_count(self) -> int:
        return int(self._deck.key_count())

    def open(self) -> None:
        if not self._open:
            self._deck.open()
            self._deck.reset()
            self._deck.set_key_callback(self._on_press)
            self._open = True

    def close(self) -> None:
        if self._open:
            try:
                self._deck.reset()
            finally:
                self._deck.close()
            self._open = False

    def set_key_image(self, key: int, image: Image.Image) -> None:
        if not 0 <= key < self.key_count:
            raise IndexError(f"key {key} out of range 0..{self.key_count - 1}")
        # Some MK.2 keys want a 90/180 rotation depending on firmware; PILHelper
        # encapsulates that. We pass our 72×72 RGB image; PILHelper converts to
        # the device's native JPEG bytes.
        native = PILHelper.to_native_key_format(self._deck, image)
        self._deck.set_key_image(key, native)

    def register_key_callback(self, callback: KeyCallback) -> None:
        self._callbacks.append(callback)

    def _on_press(self, _deck: Any, key: int, state: bool) -> None:
        ev = KeyEvent(key=key, pressed=state)
        for cb in list(self._callbacks):
            cb(ev)

    def _blank_all_keys(self) -> None:
        """Push a black image to every key. Used during teardown."""
        blank = Image.new("RGB", (72, 72), "#000000")
        for i in range(self.key_count):
            try:
                self.set_key_image(i, blank)
            except Exception:
                # Best-effort - don't mask shutdown problems on a single key
                pass
```

Note: `PILHelper.to_native_key_format` is the correct name in `streamdeck>=0.9.5`. Older versions exposed `PILHelper.to_native_format`. If `pip install -e ".[dev]"` resolved an older release, the AttributeError will surface during smoke testing and you can swap to `to_native_format` and pin a version range. Don't preempt; verify at test time.

- [ ] **Step 2: Update `src/sdac/device/__init__.py`**

```python
"""Device abstraction + concrete implementations."""

from sdac.device.base import Device, KeyCallback, KeyEvent
from sdac.device.mock import MockDevice
from sdac.device.streamdeck import DeviceNotFoundError, StreamDeckDevice

__all__ = [
    "Device",
    "DeviceNotFoundError",
    "KeyCallback",
    "KeyEvent",
    "MockDevice",
    "StreamDeckDevice",
]
```

- [ ] **Step 3: Add a single import-smoke test - append to `tests/unit/test_device_mock.py`**

```python
def test_streamdeckdevice_imports():
    """The real wrapper module should import even without a device attached."""
    from sdac.device.streamdeck import DeviceNotFoundError, StreamDeckDevice  # noqa: F401
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_device_mock.py -v
```

Expected: 6 passing.

- [ ] **Step 5: mypy clean**

```bash
mypy src
```

If mypy complains about `streamdeck` lacking stubs, suppress the two `from StreamDeck.*` imports with `# type: ignore[import-untyped]` on just those lines. Do NOT broaden the suppression.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 35 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/device/streamdeck.py src/sdac/device/__init__.py tests/unit/test_device_mock.py
git commit -m "feat(device): real StreamDeckDevice wrapper (no HID in tests)"
```

---

## Task 4: Platform shim - Linux implementations + Windows stub

**Files:**
- Create: `src/sdac/platform/__init__.py`
- Create: `src/sdac/platform/_linux.py`
- Create: `src/sdac/platform/_windows.py`
- Create: `tests/unit/test_platform_linux.py`

- [ ] **Step 1: Write the failing test - `tests/unit/test_platform_linux.py`**

```python
"""Verify the Linux platform shim shells out to the right binaries with the
right args. We don't actually invoke xdotool/pactl/playerctl - we mock
subprocess.run and assert on the call shape.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

WINDOWS = sys.platform.startswith("win")
pytestmark = pytest.mark.skipif(WINDOWS, reason="Linux platform shim")

from sdac.platform._linux import (  # noqa: E402
    media_next,
    media_pause,
    media_play,
    media_prev,
    open_app,
    open_url,
    send_chord,
    type_text,
    volume_down,
    volume_mute,
    volume_up,
)


def test_send_chord_shells_to_xdotool():
    with patch("subprocess.run") as run:
        send_chord("ctrl+shift+t")
    run.assert_called_once_with(["xdotool", "key", "ctrl+shift+t"], check=True)


def test_type_text_shells_to_xdotool_with_clearmodifiers():
    with patch("subprocess.run") as run:
        type_text("console.log()")
    run.assert_called_once_with(
        ["xdotool", "type", "--clearmodifiers", "--", "console.log()"], check=True
    )


def test_volume_up_pactl_with_step():
    with patch("subprocess.run") as run:
        volume_up(step=5)
    run.assert_called_once_with(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], check=True
    )


def test_volume_down_pactl_with_step():
    with patch("subprocess.run") as run:
        volume_down(step=10)
    run.assert_called_once_with(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], check=True
    )


def test_volume_mute_toggles():
    with patch("subprocess.run") as run:
        volume_mute()
    run.assert_called_once_with(
        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True
    )


def test_media_play_uses_playerctl():
    with patch("subprocess.run") as run:
        media_play()
    run.assert_called_once_with(["playerctl", "play"], check=True)


def test_media_pause_uses_playerctl():
    with patch("subprocess.run") as run:
        media_pause()
    run.assert_called_once_with(["playerctl", "pause"], check=True)


def test_media_next_uses_playerctl():
    with patch("subprocess.run") as run:
        media_next()
    run.assert_called_once_with(["playerctl", "next"], check=True)


def test_media_prev_uses_playerctl():
    with patch("subprocess.run") as run:
        media_prev()
    run.assert_called_once_with(["playerctl", "previous"], check=True)


def test_open_url_uses_webbrowser():
    with patch("webbrowser.open") as wb:
        open_url("https://example.com")
    wb.assert_called_once_with("https://example.com")


def test_open_app_starts_detached():
    with patch("subprocess.Popen") as popen:
        open_app("/usr/bin/code")
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0] == ["/usr/bin/code"]
    assert kwargs.get("start_new_session") is True
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/unit/test_platform_linux.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `src/sdac/platform/_linux.py`**

```python
"""Linux implementations of platform-dependent action primitives.

Every function shells out and raises CalledProcessError on failure so the
action dispatcher can surface that to the user. We do NOT swallow errors here.
"""

from __future__ import annotations

import subprocess
import webbrowser


def send_chord(keys: str) -> None:
    """Send a keystroke chord (e.g. 'ctrl+shift+t')."""
    subprocess.run(["xdotool", "key", keys], check=True)


def type_text(text: str) -> None:
    """Type a literal string. Uses --clearmodifiers so a held key doesn't corrupt input."""
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text], check=True)


def volume_up(step: int = 5) -> None:
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step}%"], check=True)


def volume_down(step: int = 5) -> None:
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step}%"], check=True)


def volume_mute() -> None:
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True)


def media_play() -> None:
    subprocess.run(["playerctl", "play"], check=True)


def media_pause() -> None:
    subprocess.run(["playerctl", "pause"], check=True)


def media_next() -> None:
    subprocess.run(["playerctl", "next"], check=True)


def media_prev() -> None:
    subprocess.run(["playerctl", "previous"], check=True)


def open_url(url: str) -> None:
    webbrowser.open(url)


def open_app(path: str) -> None:
    """Launch a binary detached so the daemon doesn't reap its lifecycle."""
    subprocess.Popen([path], start_new_session=True)
```

- [ ] **Step 4: Write `src/sdac/platform/_windows.py`** (stub for Phase 4)

```python
"""Windows stubs. Phase 4 fills these in with pywin32 / SendKeys equivalents."""

from __future__ import annotations


def _todo(name: str) -> None:
    raise NotImplementedError(f"platform function {name!r} not implemented on Windows (Phase 4)")


def send_chord(keys: str) -> None:  # noqa: ARG001
    _todo("send_chord")


def type_text(text: str) -> None:  # noqa: ARG001
    _todo("type_text")


def volume_up(step: int = 5) -> None:  # noqa: ARG001
    _todo("volume_up")


def volume_down(step: int = 5) -> None:  # noqa: ARG001
    _todo("volume_down")


def volume_mute() -> None:
    _todo("volume_mute")


def media_play() -> None:
    _todo("media_play")


def media_pause() -> None:
    _todo("media_pause")


def media_next() -> None:
    _todo("media_next")


def media_prev() -> None:
    _todo("media_prev")


def open_url(url: str) -> None:  # noqa: ARG001
    _todo("open_url")


def open_app(path: str) -> None:  # noqa: ARG001
    _todo("open_app")
```

- [ ] **Step 5: Write `src/sdac/platform/__init__.py`**

```python
"""Platform-dependent primitives. Selects the right backend at import time."""

from __future__ import annotations

import sys

if sys.platform.startswith("win"):
    from sdac.platform._windows import (
        media_next,
        media_pause,
        media_play,
        media_prev,
        open_app,
        open_url,
        send_chord,
        type_text,
        volume_down,
        volume_mute,
        volume_up,
    )
else:
    from sdac.platform._linux import (
        media_next,
        media_pause,
        media_play,
        media_prev,
        open_app,
        open_url,
        send_chord,
        type_text,
        volume_down,
        volume_mute,
        volume_up,
    )

__all__ = [
    "media_next",
    "media_pause",
    "media_play",
    "media_prev",
    "open_app",
    "open_url",
    "send_chord",
    "type_text",
    "volume_down",
    "volume_mute",
    "volume_up",
]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_platform_linux.py -v
```

Expected: 11 passing.

- [ ] **Step 7: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 46 tests passing.

- [ ] **Step 8: Commit**

```bash
git add src/sdac/platform/ tests/unit/test_platform_linux.py
git commit -m "feat(platform): Linux shell-out shim + Windows NotImplementedError stub"
```

---

## Task 5: Action registry + base protocols

**Files:**
- Create: `src/sdac/actions/__init__.py`
- Create: `src/sdac/actions/base.py`
- Create: `tests/unit/test_actions_registry.py`

- [ ] **Step 1: Write the failing test - `tests/unit/test_actions_registry.py`**

```python
from __future__ import annotations

import pytest

from sdac.actions import HANDLERS, get_handler, register
from sdac.actions.base import ActionHandler, DaemonContext
from sdac.config import ShellAction


class _FakeCtx:
    """A DaemonContext implementation for tests."""

    def __init__(self) -> None:
        self.page_switches: list[str] = []
        self.profile_switches: list[str] = []

    def switch_page(self, name: str) -> None:
        self.page_switches.append(name)

    def switch_profile(self, name: str) -> None:
        self.profile_switches.append(name)


def test_register_decorator_adds_to_handlers():
    initial = set(HANDLERS)

    @register
    class _Dummy:
        action_type = "_dummy"

        def execute(self, action, ctx):  # noqa: ARG002
            pass

    try:
        assert "_dummy" in HANDLERS
        assert isinstance(HANDLERS["_dummy"], _Dummy)
    finally:
        HANDLERS.pop("_dummy", None)
    assert set(HANDLERS) == initial


def test_get_handler_returns_registered_instance():
    @register
    class _Echo:
        action_type = "_echo"
        executed: list = []

        def execute(self, action, ctx):  # noqa: ARG002
            self.executed.append(action)

    try:
        h = get_handler("_echo")
        action = ShellAction(type="shell", cmd="echo hi")
        h.execute(action, _FakeCtx())
        assert h.executed == [action]
    finally:
        HANDLERS.pop("_echo", None)


def test_get_handler_unknown_type_raises_key_error():
    with pytest.raises(KeyError, match="no handler"):
        get_handler("does.not.exist")


def test_daemon_context_protocol_is_runtime_checkable():
    ctx = _FakeCtx()
    assert isinstance(ctx, DaemonContext)


def test_action_handler_protocol_is_runtime_checkable():
    @register
    class _Y:
        action_type = "_y"

        def execute(self, action, ctx):  # noqa: ARG002
            pass

    try:
        assert isinstance(HANDLERS["_y"], ActionHandler)
    finally:
        HANDLERS.pop("_y", None)
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_actions_registry.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `src/sdac/actions/base.py`**

```python
"""Action handler protocol and DaemonContext protocol.

Handlers receive a typed action and a DaemonContext that exposes only the
methods they may call back into. This keeps actions and the daemon
loosely coupled.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable


@runtime_checkable
class DaemonContext(Protocol):
    """The subset of the daemon that action handlers are allowed to call."""

    def switch_page(self, name: str) -> None: ...

    def switch_profile(self, name: str) -> None: ...


@runtime_checkable
class ActionHandler(Protocol):
    """Each handler advertises its action_type and implements execute()."""

    action_type: ClassVar[str]

    def execute(self, action: Any, ctx: DaemonContext) -> None: ...
```

- [ ] **Step 4: Write `src/sdac/actions/__init__.py`**

```python
"""Action handler registry.

Handler modules register themselves by decorating their class with
`@register`. Importing the registry imports every concrete handler module
as a side effect (see the `from sdac.actions import ...` imports at the
bottom).
"""

from __future__ import annotations

from sdac.actions.base import ActionHandler

HANDLERS: dict[str, ActionHandler] = {}


def register(cls: type) -> type:
    """Class decorator that instantiates the handler and adds it to HANDLERS."""
    instance = cls()
    HANDLERS[cls.action_type] = instance  # type: ignore[assignment]
    return cls


def get_handler(action_type: str) -> ActionHandler:
    """Look up a registered handler by its action_type. Raises KeyError if unknown."""
    try:
        return HANDLERS[action_type]
    except KeyError as e:
        raise KeyError(f"no handler registered for action type {action_type!r}") from e
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_actions_registry.py -v
```

Expected: 5 passing.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 51 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/actions/__init__.py src/sdac/actions/base.py tests/unit/test_actions_registry.py
git commit -m "feat(actions): registry + ActionHandler/DaemonContext protocols"
```

---

## Task 6: Shell action handler

**Files:**
- Create: `src/sdac/actions/shell.py`
- Modify: `src/sdac/actions/__init__.py` (eager-import the handler module)
- Create: `tests/unit/test_action_shell.py`

- [ ] **Step 1: Write the failing test - `tests/unit/test_action_shell.py`**

```python
from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401 - ensures handlers are registered
from sdac.actions import get_handler
from sdac.config import ShellAction


class _NullCtx:
    def switch_page(self, name: str) -> None:
        pass

    def switch_profile(self, name: str) -> None:
        pass


def test_shell_action_invokes_subprocess_run_with_shell_true():
    action = ShellAction(type="shell", cmd="echo hi")
    with patch("subprocess.run") as run:
        get_handler("shell").execute(action, _NullCtx())
    run.assert_called_once()
    args, kwargs = run.call_args
    assert args[0] == "echo hi"
    assert kwargs.get("shell") is True
    assert kwargs.get("check") is True


def test_shell_action_with_cwd_passes_cwd_to_subprocess():
    action = ShellAction(type="shell", cmd="ls", cwd="/tmp")
    with patch("subprocess.run") as run:
        get_handler("shell").execute(action, _NullCtx())
    _, kwargs = run.call_args
    assert kwargs.get("cwd") == "/tmp"


def test_shell_action_with_custom_shell():
    action = ShellAction(type="shell", cmd="echo hi", shell="/bin/zsh")
    with patch("subprocess.run") as run:
        get_handler("shell").execute(action, _NullCtx())
    _, kwargs = run.call_args
    assert kwargs.get("executable") == "/bin/zsh"
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_action_shell.py -v
```

Expected: `KeyError: "no handler registered for action type 'shell'"` (registry doesn't auto-import handlers yet).

- [ ] **Step 3: Write `src/sdac/actions/shell.py`**

```python
"""Shell action: run a command via the shell."""

from __future__ import annotations

import subprocess
from typing import ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import ShellAction


@register
class ShellHandler:
    action_type: ClassVar[str] = "shell"

    def execute(self, action: ShellAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        kwargs: dict = {"shell": True, "check": True}
        if action.cwd:
            kwargs["cwd"] = action.cwd
        if action.shell:
            kwargs["executable"] = action.shell
        subprocess.run(action.cmd, **kwargs)
```

- [ ] **Step 4: Eager-import the handler module from `sdac/actions/__init__.py`**

Append to `src/sdac/actions/__init__.py` (at the very bottom, after the existing definitions):

```python
# Eager imports - every concrete handler module's `@register` runs at import.
# Order is irrelevant but keep alphabetical for tidiness.
from sdac.actions import shell  # noqa: E402, F401
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_action_shell.py -v
```

Expected: 3 passing.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 54 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/actions/shell.py src/sdac/actions/__init__.py tests/unit/test_action_shell.py
git commit -m "feat(actions): shell handler"
```

---

## Task 7: Key chord + key text action handlers

**Files:**
- Create: `src/sdac/actions/keys.py`
- Modify: `src/sdac/actions/__init__.py`
- Create: `tests/unit/test_action_keys.py`

- [ ] **Step 1: Write failing test - `tests/unit/test_action_keys.py`**

```python
from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import KeyChordAction, KeyTextAction


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...


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
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_action_keys.py -v
```

Expected: `KeyError: "no handler registered for action type 'key.chord'"`.

- [ ] **Step 3: Write `src/sdac/actions/keys.py`**

```python
"""Keyboard chord and text actions."""

from __future__ import annotations

from typing import ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import KeyChordAction, KeyTextAction
from sdac.platform import send_chord, type_text


@register
class KeyChordHandler:
    action_type: ClassVar[str] = "key.chord"

    def execute(self, action: KeyChordAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        send_chord(action.keys)


@register
class KeyTextHandler:
    action_type: ClassVar[str] = "key.text"

    def execute(self, action: KeyTextAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        type_text(action.text)
```

- [ ] **Step 4: Add `keys` to the eager-import list in `sdac/actions/__init__.py`**

Update the eager-import block to:

```python
from sdac.actions import keys, shell  # noqa: E402, F401
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_action_keys.py -v
```

Expected: 2 passing.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 56 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/actions/keys.py src/sdac/actions/__init__.py tests/unit/test_action_keys.py
git commit -m "feat(actions): key.chord + key.text handlers"
```

---

## Task 8: Open URL + open app action handlers

**Files:**
- Create: `src/sdac/actions/opening.py`
- Modify: `src/sdac/actions/__init__.py`
- Create: `tests/unit/test_action_opening.py`

- [ ] **Step 1: Write failing test - `tests/unit/test_action_opening.py`**

```python
from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import OpenAppAction, OpenUrlAction


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...


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


def test_open_app_with_name_falls_back_to_xdg_open(tmp_path):
    action = OpenAppAction(type="open.app", name="firefox")
    with patch("subprocess.Popen") as popen:
        get_handler("open.app").execute(action, _NullCtx())
    args, kwargs = popen.call_args
    assert args[0] == ["xdg-open", "firefox"]
    assert kwargs.get("start_new_session") is True
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_action_opening.py -v
```

Expected: KeyError.

- [ ] **Step 3: Write `src/sdac/actions/opening.py`**

```python
"""URL and application launch actions."""

from __future__ import annotations

import subprocess
from typing import ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import OpenAppAction, OpenUrlAction
from sdac.platform import open_app, open_url


@register
class OpenUrlHandler:
    action_type: ClassVar[str] = "open.url"

    def execute(self, action: OpenUrlAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        open_url(action.url)


@register
class OpenAppHandler:
    action_type: ClassVar[str] = "open.app"

    def execute(self, action: OpenAppAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        if action.path:
            open_app(action.path)
            return
        # Fallback: open by application name via xdg-open
        assert action.name is not None  # Pydantic validator guarantees one of path/name
        subprocess.Popen(["xdg-open", action.name], start_new_session=True)
```

- [ ] **Step 4: Add `opening` to the eager-import block**

```python
from sdac.actions import keys, opening, shell  # noqa: E402, F401
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_action_opening.py -v
```

Expected: 3 passing.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 59 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/actions/opening.py src/sdac/actions/__init__.py tests/unit/test_action_opening.py
git commit -m "feat(actions): open.url + open.app handlers"
```

---

## Task 9: System volume + media key action handlers

**Files:**
- Create: `src/sdac/actions/system_audio.py`
- Modify: `src/sdac/actions/__init__.py`
- Create: `tests/unit/test_action_system_audio.py`

- [ ] **Step 1: Write failing test - `tests/unit/test_action_system_audio.py`**

```python
from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import (
    MediaNextAction,
    MediaPauseAction,
    MediaPlayAction,
    MediaPrevAction,
    SystemVolumeDownAction,
    SystemVolumeMuteAction,
    SystemVolumeUpAction,
)


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...


def test_volume_up_calls_platform_volume_up_with_step():
    action = SystemVolumeUpAction(type="system.volume.up", step=7)
    with patch("sdac.actions.system_audio.volume_up") as f:
        get_handler("system.volume.up").execute(action, _NullCtx())
    f.assert_called_once_with(step=7)


def test_volume_down_passes_step():
    action = SystemVolumeDownAction(type="system.volume.down")  # default step=5
    with patch("sdac.actions.system_audio.volume_down") as f:
        get_handler("system.volume.down").execute(action, _NullCtx())
    f.assert_called_once_with(step=5)


def test_volume_mute_no_args():
    action = SystemVolumeMuteAction(type="system.volume.mute")
    with patch("sdac.actions.system_audio.volume_mute") as f:
        get_handler("system.volume.mute").execute(action, _NullCtx())
    f.assert_called_once_with()


def test_media_play():
    action = MediaPlayAction(type="media.play")
    with patch("sdac.actions.system_audio.media_play") as f:
        get_handler("media.play").execute(action, _NullCtx())
    f.assert_called_once_with()


def test_media_pause():
    action = MediaPauseAction(type="media.pause")
    with patch("sdac.actions.system_audio.media_pause") as f:
        get_handler("media.pause").execute(action, _NullCtx())
    f.assert_called_once_with()


def test_media_next():
    action = MediaNextAction(type="media.next")
    with patch("sdac.actions.system_audio.media_next") as f:
        get_handler("media.next").execute(action, _NullCtx())
    f.assert_called_once_with()


def test_media_prev():
    action = MediaPrevAction(type="media.prev")
    with patch("sdac.actions.system_audio.media_prev") as f:
        get_handler("media.prev").execute(action, _NullCtx())
    f.assert_called_once_with()
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_action_system_audio.py -v
```

Expected: KeyError.

- [ ] **Step 3: Write `src/sdac/actions/system_audio.py`**

```python
"""System volume and media-key actions."""

from __future__ import annotations

from typing import ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import (
    MediaNextAction,
    MediaPauseAction,
    MediaPlayAction,
    MediaPrevAction,
    SystemVolumeDownAction,
    SystemVolumeMuteAction,
    SystemVolumeUpAction,
)
from sdac.platform import (
    media_next,
    media_pause,
    media_play,
    media_prev,
    volume_down,
    volume_mute,
    volume_up,
)


@register
class SystemVolumeUpHandler:
    action_type: ClassVar[str] = "system.volume.up"

    def execute(self, action: SystemVolumeUpAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        volume_up(step=action.step)


@register
class SystemVolumeDownHandler:
    action_type: ClassVar[str] = "system.volume.down"

    def execute(self, action: SystemVolumeDownAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        volume_down(step=action.step)


@register
class SystemVolumeMuteHandler:
    action_type: ClassVar[str] = "system.volume.mute"

    def execute(self, action: SystemVolumeMuteAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        volume_mute()


@register
class MediaPlayHandler:
    action_type: ClassVar[str] = "media.play"

    def execute(self, action: MediaPlayAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        media_play()


@register
class MediaPauseHandler:
    action_type: ClassVar[str] = "media.pause"

    def execute(self, action: MediaPauseAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        media_pause()


@register
class MediaNextHandler:
    action_type: ClassVar[str] = "media.next"

    def execute(self, action: MediaNextAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        media_next()


@register
class MediaPrevHandler:
    action_type: ClassVar[str] = "media.prev"

    def execute(self, action: MediaPrevAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        media_prev()
```

- [ ] **Step 4: Add to eager-import block**

```python
from sdac.actions import keys, opening, shell, system_audio  # noqa: E402, F401
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_action_system_audio.py -v
```

Expected: 7 passing.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 66 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/actions/system_audio.py src/sdac/actions/__init__.py tests/unit/test_action_system_audio.py
git commit -m "feat(actions): system volume + media key handlers"
```

---

## Task 10: Compound action handler + navigation handlers

**Files:**
- Create: `src/sdac/actions/compound.py`
- Create: `src/sdac/actions/navigation.py`
- Modify: `src/sdac/actions/__init__.py`
- Create: `tests/unit/test_action_compound.py`
- Create: `tests/unit/test_action_navigation.py`

- [ ] **Step 1: Write failing test - `tests/unit/test_action_compound.py`**

```python
from __future__ import annotations

from unittest.mock import patch

import pytest

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import CompoundAction, ShellAction


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...


def test_compound_runs_actions_in_order():
    actions = [
        ShellAction(type="shell", cmd="echo 1"),
        ShellAction(type="shell", cmd="echo 2"),
    ]
    compound = CompoundAction(type="compound", actions=actions)
    with patch("subprocess.run") as run:
        get_handler("compound").execute(compound, _NullCtx())
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == "echo 1"
    assert run.call_args_list[1].args[0] == "echo 2"


def test_compound_stops_on_first_failure_by_default():
    import subprocess

    actions = [
        ShellAction(type="shell", cmd="fail"),
        ShellAction(type="shell", cmd="never"),
    ]
    compound = CompoundAction(type="compound", actions=actions)
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "fail")):
        with pytest.raises(subprocess.CalledProcessError):
            get_handler("compound").execute(compound, _NullCtx())


def test_compound_continue_on_error_runs_all():
    import subprocess

    actions = [
        ShellAction(type="shell", cmd="fail"),
        ShellAction(type="shell", cmd="next"),
    ]
    compound = CompoundAction(type="compound", actions=actions, continue_on_error=True)
    calls: list = []
    def fake(cmd, **kwargs):  # noqa: ARG001
        calls.append(cmd)
        if cmd == "fail":
            raise subprocess.CalledProcessError(1, cmd)
    with patch("subprocess.run", side_effect=fake):
        get_handler("compound").execute(compound, _NullCtx())
    assert calls == ["fail", "next"]
```

- [ ] **Step 2: Write failing test - `tests/unit/test_action_navigation.py`**

```python
from __future__ import annotations

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import PageGoAction, ProfileSwitchAction


class _RecordingCtx:
    def __init__(self) -> None:
        self.pages: list[str] = []
        self.profiles: list[str] = []

    def switch_page(self, name: str) -> None:
        self.pages.append(name)

    def switch_profile(self, name: str) -> None:
        self.profiles.append(name)


def test_page_go_calls_ctx_switch_page():
    ctx = _RecordingCtx()
    action = PageGoAction(type="page.go", page="git")
    get_handler("page.go").execute(action, ctx)
    assert ctx.pages == ["git"]
    assert ctx.profiles == []


def test_profile_switch_calls_ctx_switch_profile():
    ctx = _RecordingCtx()
    action = ProfileSwitchAction(type="profile.switch", profile="streaming")
    get_handler("profile.switch").execute(action, ctx)
    assert ctx.profiles == ["streaming"]
    assert ctx.pages == []
```

- [ ] **Step 3: Run failing**

```bash
pytest tests/unit/test_action_compound.py tests/unit/test_action_navigation.py -v
```

Expected: KeyError on the action types.

- [ ] **Step 4: Write `src/sdac/actions/compound.py`**

```python
"""Compound action: run a sequence of sub-actions."""

from __future__ import annotations

import logging
from typing import ClassVar

from sdac.actions import get_handler, register
from sdac.actions.base import DaemonContext
from sdac.config import CompoundAction

log = logging.getLogger(__name__)


@register
class CompoundHandler:
    action_type: ClassVar[str] = "compound"

    def execute(self, action: CompoundAction, ctx: DaemonContext) -> None:
        for i, sub in enumerate(action.actions):
            handler = get_handler(sub.type)
            try:
                handler.execute(sub, ctx)
            except Exception:
                if action.continue_on_error:
                    log.exception("compound sub-action %d (%s) failed; continuing", i, sub.type)
                    continue
                raise
```

- [ ] **Step 5: Write `src/sdac/actions/navigation.py`**

```python
"""Navigation actions: page.go and profile.switch.

These don't shell out - they call back into the daemon via DaemonContext.
"""

from __future__ import annotations

from typing import ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import PageGoAction, ProfileSwitchAction


@register
class PageGoHandler:
    action_type: ClassVar[str] = "page.go"

    def execute(self, action: PageGoAction, ctx: DaemonContext) -> None:
        ctx.switch_page(action.page)


@register
class ProfileSwitchHandler:
    action_type: ClassVar[str] = "profile.switch"

    def execute(self, action: ProfileSwitchAction, ctx: DaemonContext) -> None:
        ctx.switch_profile(action.profile)
```

- [ ] **Step 6: Add both to eager-import block in `sdac/actions/__init__.py`**

```python
from sdac.actions import compound, keys, navigation, opening, shell, system_audio  # noqa: E402, F401
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/unit/test_action_compound.py tests/unit/test_action_navigation.py -v
```

Expected: 5 passing.

- [ ] **Step 8: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 71 tests passing.

- [ ] **Step 9: Commit**

```bash
git add src/sdac/actions/compound.py src/sdac/actions/navigation.py \
        src/sdac/actions/__init__.py \
        tests/unit/test_action_compound.py tests/unit/test_action_navigation.py
git commit -m "feat(actions): compound + page.go + profile.switch handlers"
```

---

## Task 11: OBS action stub handlers (raise NotImplementedError)

**Files:**
- Create: `src/sdac/actions/obs.py`
- Modify: `src/sdac/actions/__init__.py`

(No tests - these only exist so the registry can resolve every action type the schema admits, and so the daemon doesn't blow up at dispatch time with KeyError. Each handler raises a clear NotImplementedError telling the user that OBS support arrives in Phase 3. Tests would just assert "raises NotImplementedError", which is low-value.)

- [ ] **Step 1: Write `src/sdac/actions/obs.py`**

```python
"""OBS action stubs.

Phase 3 replaces every body here with real obs-cmd shell-outs / async
websocket calls. The handlers exist now so dispatch doesn't KeyError on
configs that already use the obs.* schema.
"""

from __future__ import annotations

from typing import ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import (
    ObsInputMuteToggleAction,
    ObsRecordingToggleAction,
    ObsReplaySaveAction,
    ObsSceneSwitchAction,
    ObsStreamingToggleAction,
    ObsVirtualCamToggleAction,
)


def _not_yet(name: str) -> None:
    raise NotImplementedError(
        f"OBS action {name!r} is not implemented in Phase 2a; ships in Phase 3"
    )


@register
class ObsSceneSwitchHandler:
    action_type: ClassVar[str] = "obs.scene.switch"

    def execute(self, action: ObsSceneSwitchAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        _not_yet("obs.scene.switch")


@register
class ObsRecordingToggleHandler:
    action_type: ClassVar[str] = "obs.recording.toggle"

    def execute(self, action: ObsRecordingToggleAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        _not_yet("obs.recording.toggle")


@register
class ObsStreamingToggleHandler:
    action_type: ClassVar[str] = "obs.streaming.toggle"

    def execute(self, action: ObsStreamingToggleAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        _not_yet("obs.streaming.toggle")


@register
class ObsReplaySaveHandler:
    action_type: ClassVar[str] = "obs.replay.save"

    def execute(self, action: ObsReplaySaveAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        _not_yet("obs.replay.save")


@register
class ObsVirtualCamToggleHandler:
    action_type: ClassVar[str] = "obs.virtualcam.toggle"

    def execute(self, action: ObsVirtualCamToggleAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        _not_yet("obs.virtualcam.toggle")


@register
class ObsInputMuteToggleHandler:
    action_type: ClassVar[str] = "obs.input.mute.toggle"

    def execute(self, action: ObsInputMuteToggleAction, ctx: DaemonContext) -> None:  # noqa: ARG002
        _not_yet("obs.input.mute.toggle")
```

- [ ] **Step 2: Add to eager-import block**

```python
from sdac.actions import (  # noqa: E402, F401
    compound,
    keys,
    navigation,
    obs,
    opening,
    shell,
    system_audio,
)
```

- [ ] **Step 3: Verify registry sees all 20 action types** (every action type from the schema is registered)

```bash
python -c "import sdac.actions; print(sorted(sdac.actions.HANDLERS))"
```

Expected 20 entries (every action type the discriminated union covers):
```
['compound', 'key.chord', 'key.text', 'media.next', 'media.pause', 'media.play',
 'media.prev', 'obs.input.mute.toggle', 'obs.recording.toggle', 'obs.replay.save',
 'obs.scene.switch', 'obs.streaming.toggle', 'obs.virtualcam.toggle',
 'open.app', 'open.url', 'page.go', 'profile.switch', 'shell',
 'system.volume.down', 'system.volume.mute', 'system.volume.up']
```

That's 21 - the spec said 21 action types and we have all of them. If the count differs, STOP and audit.

- [ ] **Step 4: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 71 tests still passing.

- [ ] **Step 5: Commit**

```bash
git add src/sdac/actions/obs.py src/sdac/actions/__init__.py
git commit -m "feat(actions): OBS handler stubs (raise until Phase 3)"
```

---

## Task 12: Daemon orchestrator core

**Files:**
- Create: `src/sdac/daemon.py`
- Create: `tests/unit/test_daemon.py`

- [ ] **Step 1: Write failing test - `tests/unit/test_daemon.py`**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import sdac.actions  # noqa: F401
from sdac.daemon import Daemon
from sdac.device import MockDevice
from sdac.errors import ConfigError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_daemon_loads_config_and_renders_default_profile_home_page():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    # comprehensive.yaml's default profile is `coding` with `home` page; the
    # home page configures 8 keys (indices 0..7). The mock should have 8 images
    # pushed plus blanks for keys 8..14.
    assert device.is_open  # render_current_page opens implicitly
    assert set(device.images_pushed.keys()) == set(range(15))


def test_daemon_dispatches_key_press_to_handler():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    with patch("subprocess.run") as run:
        device.inject_press(0)  # key 0 on coding/home is a shell action
    # The press fires once; release shouldn't dispatch again.
    assert run.call_count == 1


def test_daemon_page_go_navigates_within_profile():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    device.images_pushed.clear()
    # key 5 on coding/home has action page.go(page=git)
    device.inject_press(5)
    assert d.current_page == "git"
    # render after page change pushed all 15 keys again
    assert set(device.images_pushed.keys()) == set(range(15))


def test_daemon_profile_switch_changes_profile_and_resets_to_default_page():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    # key 6 on coding/home has action profile.switch(profile=streaming)
    device.inject_press(6)
    assert d.current_profile == "streaming"
    assert d.current_page == "home"  # streaming.default_page


def test_daemon_load_propagates_config_error_on_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 99\n")
    device = MockDevice()
    d = Daemon(device=device, config_path=bad)
    with pytest.raises(ConfigError):
        d.load()


def test_daemon_handler_exception_does_not_crash_daemon(caplog):
    """An action that raises must be logged but the daemon stays up."""
    import logging

    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()

    def boom(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="sdac.daemon"):
        with patch("subprocess.run", side_effect=boom):
            device.inject_press(0)
    assert any("boom" in rec.message or "boom" in str(rec.exc_info) for rec in caplog.records)
    # Daemon is still wired up - a follow-on press still dispatches
    with patch("subprocess.run") as run:
        device.inject_press(1)
    assert run.call_count == 1  # key.chord action; xdotool was patched as subprocess.run

```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_daemon.py -v
```

Expected: ImportError on `sdac.daemon`.

- [ ] **Step 3: Write `src/sdac/daemon.py`**

```python
"""Daemon orchestrator.

Owns the device and config. Handles key-press dispatch via the action registry.
The daemon is synchronous: key callbacks (from the device's HID thread or a
mock's direct call) run handlers in-line. Phase 3 will add background
event loops for OBS websocket subscriptions.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PIL import Image

from sdac.actions import get_handler
from sdac.config import Config, load_config
from sdac.device import Device, KeyEvent
from sdac.render import KEY_SIZE, render_key

log = logging.getLogger(__name__)


class Daemon:
    """Cross-platform Stream Deck driver.

    Phase 2a behavior: load config, render the default profile/page, dispatch
    presses, allow handlers to navigate via switch_page / switch_profile.
    Phase 2a does NOT yet watch the config file (Task 13) or recover from
    device unplug (Task 14).
    """

    def __init__(self, device: Device, config_path: str | Path) -> None:
        self._device = device
        self._config_path = Path(config_path)
        self._config: Config | None = None
        self._current_profile: str | None = None
        self._current_page: str | None = None
        self._lock = threading.RLock()
        # Internal: drop key.released events (we only act on press)
        self._device.register_key_callback(self._on_key)

    # ----- DaemonContext protocol -----

    def switch_page(self, name: str) -> None:
        with self._lock:
            assert self._config is not None and self._current_profile is not None
            profile = self._config.profiles[self._current_profile]
            if name not in profile.pages:
                log.error("switch_page: page %r not in profile %r", name, self._current_profile)
                return
            self._current_page = name
        self.render_current_page()

    def switch_profile(self, name: str) -> None:
        with self._lock:
            assert self._config is not None
            if name not in self._config.profiles:
                log.error("switch_profile: profile %r not found", name)
                return
            self._current_profile = name
            self._current_page = self._config.profiles[name].default_page
        self.render_current_page()

    # ----- Lifecycle -----

    def load(self) -> None:
        """Parse the config file and reset to its default profile/page."""
        cfg = load_config(self._config_path)
        with self._lock:
            self._config = cfg
            self._current_profile = cfg.default_profile
            self._current_page = cfg.profiles[cfg.default_profile].default_page

    @property
    def current_profile(self) -> str | None:
        return self._current_profile

    @property
    def current_page(self) -> str | None:
        return self._current_page

    # ----- Rendering -----

    def render_current_page(self) -> None:
        """Push an image for every key on the current page (blanks for empty slots)."""
        with self._lock:
            assert self._config is not None
            assert self._current_profile is not None
            assert self._current_page is not None
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            keys = dict(page.keys)
        if not self._device.is_open:
            self._device.open()
        blank = Image.new("RGB", (KEY_SIZE, KEY_SIZE), "#000000")
        for idx in range(self._device.key_count):
            if idx in keys:
                img = render_key(keys[idx], state="idle")
            else:
                img = blank
            try:
                self._device.set_key_image(idx, img)
            except Exception:
                log.exception("failed to set key %d image", idx)

    # ----- Key dispatch -----

    def _on_key(self, event: KeyEvent) -> None:
        if not event.pressed:
            return
        with self._lock:
            if self._config is None or self._current_profile is None or self._current_page is None:
                return
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            key_cfg = page.keys.get(event.key)
        if key_cfg is None:
            return
        try:
            handler = get_handler(key_cfg.action.type)
            handler.execute(key_cfg.action, self)
        except Exception:
            log.exception("action %r on key %d raised", key_cfg.action.type, event.key)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_daemon.py -v
```

Expected: 6 passing. If `test_daemon_handler_exception_does_not_crash_daemon` is flaky because the second `device.inject_press(1)` triggers the real `subprocess.run` (xdotool isn't installed in CI), wrap that call too:

If you get `FileNotFoundError: 'xdotool'`, the test is asserting wrong. The second press in that test is `key 1` which has action `key.chord`. Replace its assertion block with: `with patch("sdac.platform._linux.subprocess.run") as run: ...` and the call shape: `run.assert_called_once()`. Make sure the implementation goes through the platform layer cleanly so this works.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 77 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/daemon.py tests/unit/test_daemon.py
git commit -m "feat(daemon): orchestrator with key dispatch and navigation"
```

---

## Task 13: Hot reload via watchdog

**Files:**
- Modify: `src/sdac/daemon.py`
- Modify: `tests/unit/test_daemon.py`

- [ ] **Step 1: Write failing test - append to `tests/unit/test_daemon.py`**

```python
def test_daemon_hot_reload_picks_up_new_config(tmp_path: Path):
    cfg_path = tmp_path / "live.yaml"
    cfg_path.write_text(
        "version: 1\n"
        "default_profile: a\n"
        "profiles:\n"
        "  a:\n"
        "    default_page: home\n"
        "    pages:\n"
        "      home:\n"
        "        keys:\n"
        "          0:\n"
        "            icon: {text: A}\n"
        "            action: {type: shell, cmd: \"true\"}\n"
    )
    device = MockDevice()
    d = Daemon(device=device, config_path=cfg_path)
    d.load()
    d.render_current_page()
    d.start_watching()

    # rewrite config so default_profile changes
    cfg_path.write_text(
        "version: 1\n"
        "default_profile: b\n"
        "profiles:\n"
        "  b:\n"
        "    default_page: home\n"
        "    pages:\n"
        "      home:\n"
        "        keys:\n"
        "          0:\n"
        "            icon: {text: B}\n"
        "            action: {type: shell, cmd: \"true\"}\n"
    )

    # wait up to 3 seconds for watchdog to pick up the change
    import time
    for _ in range(30):
        time.sleep(0.1)
        if d.current_profile == "b":
            break
    d.stop_watching()
    assert d.current_profile == "b"


def test_daemon_hot_reload_rejects_invalid_config_and_keeps_old(tmp_path: Path):
    cfg_path = tmp_path / "live.yaml"
    cfg_path.write_text(
        "version: 1\n"
        "default_profile: a\n"
        "profiles:\n"
        "  a:\n"
        "    default_page: home\n"
        "    pages:\n"
        "      home:\n"
        "        keys: {}\n"
    )
    device = MockDevice()
    d = Daemon(device=device, config_path=cfg_path)
    d.load()
    d.render_current_page()
    d.start_watching()

    cfg_path.write_text("version: 99\n")  # invalid

    import time
    time.sleep(0.6)  # give watchdog time to react
    d.stop_watching()

    assert d.current_profile == "a"  # unchanged
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_daemon.py -k hot_reload -v
```

Expected: AttributeError on `start_watching`.

- [ ] **Step 3: Extend `Daemon` in `src/sdac/daemon.py`**

Add to the imports:

```python
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
```

(If mypy errors on missing stubs, suppress those two import lines individually.)

Add to `Daemon.__init__`:

```python
        self._observer: Observer | None = None
```

Add these methods to `Daemon`:

```python
    def start_watching(self) -> None:
        """Begin watching the config file for changes; reload on every modify."""
        if self._observer is not None:
            return

        daemon = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):  # type: ignore[no-untyped-def]
                if Path(event.src_path).resolve() == daemon._config_path.resolve():
                    daemon._reload()

            def on_created(self, event):  # type: ignore[no-untyped-def]
                # Editors that write via rename use create-then-rename.
                if Path(event.src_path).resolve() == daemon._config_path.resolve():
                    daemon._reload()

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self._config_path.parent), recursive=False)
        self._observer.start()

    def stop_watching(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=2.0)
        self._observer = None

    def _reload(self) -> None:
        try:
            new_cfg = load_config(self._config_path)
        except Exception:
            log.exception("config reload rejected; keeping previous config")
            return
        with self._lock:
            # Try to keep the current profile/page if they still exist, otherwise reset.
            cur_profile = self._current_profile
            cur_page = self._current_page
            if cur_profile in new_cfg.profiles:
                profile = new_cfg.profiles[cur_profile]
                if cur_page not in profile.pages:
                    cur_page = profile.default_page
            else:
                cur_profile = new_cfg.default_profile
                cur_page = new_cfg.profiles[new_cfg.default_profile].default_page
            self._config = new_cfg
            self._current_profile = cur_profile
            self._current_page = cur_page
        self.render_current_page()
        log.info("config reloaded; active=%s/%s", self._current_profile, self._current_page)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_daemon.py -k hot_reload -v
```

Expected: 2 passing.

If the first test flakes (watchdog hasn't picked up the change within 3s on this machine), bump the timeout in the test to 5s. Do NOT add a `sleep` to the implementation.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 79 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/daemon.py tests/unit/test_daemon.py
git commit -m "feat(daemon): hot reload via watchdog with reject-keep-previous on invalid"
```

---

## Task 14: Device hotplug resilience

**Files:**
- Modify: `src/sdac/daemon.py`
- Modify: `src/sdac/device/streamdeck.py` (add `enumerate_first_or_none`)
- Create: `tests/unit/test_daemon_hotplug.py`

- [ ] **Step 1: Add `enumerate_first_or_none` classmethod to StreamDeckDevice**

In `src/sdac/device/streamdeck.py`, add:

```python
    @classmethod
    def enumerate_first_or_none(cls) -> StreamDeckDevice | None:
        """Like enumerate_first but returns None instead of raising."""
        decks = DeviceManager().enumerate()
        if not decks:
            return None
        return cls(decks[0])
```

- [ ] **Step 2: Write failing test - `tests/unit/test_daemon_hotplug.py`**

```python
from __future__ import annotations

from pathlib import Path

from sdac.daemon import Daemon
from sdac.device import MockDevice

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_render_after_reopen_resumes_cleanly():
    """Simulate device.close() then re-open via render_current_page()."""
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    assert device.is_open

    device.close()
    device.images_pushed.clear()

    d.render_current_page()
    assert device.is_open
    assert set(device.images_pushed.keys()) == set(range(15))


def test_set_key_image_failure_is_logged_and_skipped(caplog):
    """If set_key_image raises mid-render, daemon logs and renders other keys."""
    import logging

    class FlakyDevice(MockDevice):
        def __init__(self) -> None:
            super().__init__()
            self.fail_on_key: int | None = None

        def set_key_image(self, key, image):  # type: ignore[override]
            if key == self.fail_on_key:
                raise RuntimeError(f"simulated USB hiccup on key {key}")
            super().set_key_image(key, image)

    device = FlakyDevice()
    device.fail_on_key = 3
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    with caplog.at_level(logging.ERROR, logger="sdac.daemon"):
        d.render_current_page()
    assert 3 not in device.images_pushed
    # Other keys still rendered
    assert 0 in device.images_pushed
    assert any("key 3" in r.message or "key 3" in str(r) for r in caplog.records)
```

- [ ] **Step 3: Run failing**

```bash
pytest tests/unit/test_daemon_hotplug.py -v
```

Expected: 2 passing already? `render_current_page` was written to re-open if closed (Task 12). Verify both tests pass without further code changes. If they do, this task is mostly documentation: the resilience was baked into Task 12.

If `test_set_key_image_failure_is_logged_and_skipped` fails because the existing logging doesn't include the key index clearly, adjust the `log.exception("failed to set key %d image", idx)` in `render_current_page` so the test's substring matches.

- [ ] **Step 4: If the device disconnects DURING runtime, the next key callback won't fire - but the daemon won't crash. Add a `run_forever` loop method to `Daemon` for the `sdac daemon` CLI verb (next task uses it):**

Append to `src/sdac/daemon.py`:

```python
import signal
import time as _time


    def run_forever(self) -> None:
        """Block until SIGINT / SIGTERM. Used by the `sdac daemon` CLI verb."""
        stop = threading.Event()

        def handle(signum, frame):  # type: ignore[no-untyped-def]
            log.info("received signal %d; stopping", signum)
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, handle)

        try:
            while not stop.is_set():
                stop.wait(timeout=1.0)
        finally:
            self.stop_watching()
            if self._device.is_open:
                self._device.close()
```

(Move `import signal` and `import threading` to the top of the file - `threading` is already there from Task 12. Add `import signal`.)

- [ ] **Step 5: Run tests + full check**

```bash
pytest -q && ruff check src tests && mypy src
```

Expected: clean, 81 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/daemon.py src/sdac/device/streamdeck.py tests/unit/test_daemon_hotplug.py
git commit -m "feat(daemon): hotplug resilience + run_forever + signal handling"
```

---

## Task 15: `sdac daemon` CLI verb

**Files:**
- Modify: `src/sdac/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests - append to `tests/unit/test_cli.py`**

```python
def test_daemon_command_uses_mock_device_when_flag_set(tmp_path: Path):
    """The --mock flag is for development/CI. With it, daemon uses MockDevice
    and exits immediately (because we patch run_forever)."""
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\nprofiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    runner = CliRunner()
    from unittest.mock import patch
    with patch("sdac.daemon.Daemon.run_forever", return_value=None):
        result = runner.invoke(main, ["daemon", "--config", str(cfg), "--mock"])
    assert result.exit_code == 0, result.output
    assert "starting" in result.output.lower()


def test_daemon_command_unknown_config_errors(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_cli.py -k daemon -v
```

Expected: `UsageError("no such option: --mock")` or similar.

- [ ] **Step 3: Add `daemon` command to `src/sdac/cli.py`**

Add to imports (at top, merged cleanly):

```python
import logging
```

And add this command to the bottom of `src/sdac/cli.py`:

```python
@main.command()
@click.option("--config", "config_path",
              type=click.Path(exists=True, dir_okay=False, readable=True),
              required=True,
              help="Path to the YAML config file.")
@click.option("--mock", is_flag=True,
              help="Use an in-memory MockDevice instead of real hardware (dev / CI).")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def daemon(config_path: str, mock: bool, verbose: bool) -> None:
    """Run the Stream Deck daemon (foreground)."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if mock:
        from sdac.device import MockDevice
        device = MockDevice()
    else:
        from sdac.device import DeviceNotFoundError, StreamDeckDevice
        try:
            device = StreamDeckDevice.enumerate_first()
        except DeviceNotFoundError as e:
            click.echo(str(e), err=True)
            sys.exit(5)
    from sdac.daemon import Daemon
    d = Daemon(device=device, config_path=config_path)
    try:
        d.load()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    click.echo(f"starting daemon: {config_path} (mock={mock})")
    d.render_current_page()
    d.start_watching()
    d.run_forever()
    click.echo("daemon stopped")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_cli.py -k daemon -v
```

Expected: 2 passing.

- [ ] **Step 5: Manual smoke (mock device)**

```bash
. .venv/bin/activate
sdac daemon --config tests/fixtures/configs/comprehensive.yaml --mock -v &
SDAC_PID=$!
sleep 1
kill -TERM $SDAC_PID
wait $SDAC_PID
```

Expected: daemon starts, prints log lines, terminates on SIGTERM cleanly.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 83 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): sdac daemon verb with --mock for dev"
```

---

## Task 16: End-to-end integration test on MockDevice

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_daemon_e2e.py`
- Create: `tests/fixtures/configs/daemon_smoke.yaml`

- [ ] **Step 1: Write `tests/fixtures/configs/daemon_smoke.yaml`**

```yaml
version: 1
default_profile: main
profiles:
  main:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Shell"}
            action: {type: shell, cmd: "true"}
          1:
            icon: {text: "Chord"}
            action: {type: key.chord, keys: "ctrl+t"}
          2:
            icon: {text: "Vol+"}
            action: {type: system.volume.up, step: 2}
          3:
            icon: {text: "Compound"}
            action:
              type: compound
              actions:
                - {type: shell, cmd: "true"}
                - {type: shell, cmd: "true"}
          4:
            icon: {text: "Nav"}
            action: {type: page.go, page: other}
      other:
        keys:
          0:
            icon: {text: "Back"}
            action: {type: page.go, page: home}
```

- [ ] **Step 2: Write `tests/integration/__init__.py`** (empty file)

- [ ] **Step 3: Write `tests/integration/test_daemon_e2e.py`**

```python
"""End-to-end daemon test - exercises every handler category against MockDevice
in one run, with hot reload thrown in for good measure.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from sdac.daemon import Daemon
from sdac.device import MockDevice

FIXTURE = Path(__file__).parent.parent / "fixtures" / "configs" / "daemon_smoke.yaml"


def test_full_lifecycle_against_mock_device(tmp_path: Path):
    # Copy fixture to a writable location so we can edit it during the run.
    cfg = tmp_path / "smoke.yaml"
    cfg.write_text(FIXTURE.read_text())

    device = MockDevice()
    d = Daemon(device=device, config_path=cfg)
    d.load()
    d.render_current_page()
    d.start_watching()
    try:
        # Initial render covers all 15 keys.
        assert set(device.images_pushed.keys()) == set(range(15))

        # Shell action
        with patch("subprocess.run") as run:
            device.inject_press(0)
        assert run.call_count == 1
        assert run.call_args.args[0] == "true"

        # Chord action (goes through platform.send_chord -> subprocess.run)
        with patch("sdac.platform._linux.subprocess.run") as run:
            device.inject_press(1)
        run.assert_called_with(["xdotool", "key", "ctrl+t"], check=True)

        # Volume up
        with patch("sdac.platform._linux.subprocess.run") as run:
            device.inject_press(2)
        run.assert_called_with(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+2%"], check=True
        )

        # Compound (two shell sub-actions)
        with patch("subprocess.run") as run:
            device.inject_press(3)
        assert run.call_count == 2

        # Page navigation
        device.inject_press(4)
        assert d.current_page == "other"

        # Back-nav from the other page
        device.images_pushed.clear()
        device.inject_press(0)
        assert d.current_page == "home"

        # Hot reload: rewrite config so default_profile changes
        cfg.write_text(
            "version: 1\ndefault_profile: changed\n"
            "profiles:\n"
            "  changed:\n    default_page: only\n"
            "    pages:\n      only:\n        keys: {}\n"
        )
        for _ in range(30):
            time.sleep(0.1)
            if d.current_profile == "changed":
                break
        assert d.current_profile == "changed"
        assert d.current_page == "only"
    finally:
        d.stop_watching()
        device.close()
```

- [ ] **Step 4: Run**

```bash
pytest tests/integration/ -v
```

Expected: 1 passing.

- [ ] **Step 5: Full check (everything)**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 84 tests passing.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/ tests/fixtures/configs/daemon_smoke.yaml
git commit -m "test(integration): end-to-end daemon lifecycle on MockDevice"
```

---

## Task 17: README + docs update

**Files:**
- Modify: `README.md`
- Modify: `docs/schema.md` (note Phase 2a status changes for action execution)

- [ ] **Step 1: Update `README.md`** - change the status line + add Phase 2a quick start

Find the line `**Status:** Phase 1 (current). \`sdac validate\` + \`sdac preview\` work without a USB device.` and replace the entire status paragraph with:

```markdown
**Status:** Phase 2a (current). `sdac daemon` runs against a real Stream Deck MK.2 (Linux only). All non-OBS action types execute: shell, key.chord, key.text, open.url/app, system.volume.*, media.*, page.go, profile.switch, compound. Hot reload on config edit. Service install (systemd unit) lands in Phase 2b; OBS execution lands in Phase 3; Windows port lands in Phase 4.
```

Add a new section under `## Quick start`:

```markdown
## Daemon (Phase 2a, Linux)

Run the daemon against a plugged-in Stream Deck MK.2:

```bash
sdac daemon --config ~/.config/sdac/config.yaml -v
```

Or against an in-memory mock device (no hardware required - useful for testing your config):

```bash
sdac daemon --config ~/.config/sdac/config.yaml --mock -v
```

The daemon stays in the foreground. Use `Ctrl+C` to stop. Phase 2b will add a `sdac install-service` command that registers a systemd user unit so it autostarts at login.

Edit the config file while the daemon is running - it'll hot-reload within ~1s. Invalid configs are logged and rejected; the daemon keeps the previous valid config.
```

- [ ] **Step 2: Update `docs/schema.md`** - add a Phase 2a note about OBS action stubs

At the top of the "Actions" section, add a paragraph:

```markdown
**Phase 2a runtime note:** the `obs.*` action types validate in the schema but their handlers currently raise `NotImplementedError` at dispatch. Real OBS execution arrives in Phase 3. All other action types execute normally.
```

- [ ] **Step 3: Update existing Phase 1 line in README - strike "no USB device required"**

Find the Phase 1 capabilities section and adjust the leading paragraph:

```markdown
## Capabilities (Phase 1 + 2a)

- Validate a YAML config against the full v1 schema (Pydantic 2 discriminated union over 21 action types).
- Resolve `${ENV_VAR}` in any string field - keep passwords out of the YAML.
- Render every key in a profile/page as a single mosaic PNG (offline preview, no device required).
- Warn (or strict-reject with `--strict-perms`) when the config file is world-readable on POSIX.
- Run a daemon that owns a real Stream Deck MK.2 over USB and dispatches button presses to handlers.
- Hot-reload the config without restarting the daemon.
```

- [ ] **Step 4: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 84 tests passing.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/schema.md
git commit -m "docs: Phase 2a - daemon section + status update"
```

---

## Done criteria for Phase 2a

1. `pipx install -e .` succeeds and `sdac --help` lists `daemon`, `validate`, `preview`.
2. `sdac daemon --config <path> --mock -v` starts, logs, and exits cleanly on SIGTERM.
3. `sdac daemon --config <path>` against a plugged-in Stream Deck MK.2 renders the default profile and dispatches button presses correctly (manual smoke).
4. All non-OBS action types execute as specified. OBS action types raise `NotImplementedError` with a "Phase 3" message.
5. Hot reload works: edit the config file while the daemon runs, see the new layout within ~1s; invalid configs are rejected and the previous config persists.
6. 84+ tests passing, ruff clean, mypy clean.

## Out of scope (deferred to Phase 2b)

- `sdac install-service` / `sdac uninstall-service` (systemd user unit registration).
- `sdac doctor` (device + deps + config + service-status diagnostic).
- udev rule install for daemon-at-boot use cases.
- `--strict-perms` enforcement at daemon load (currently only at `sdac validate`).

## Deferred to Phase 3

- Real OBS action execution (currently stubs that raise `NotImplementedError`).
- Live state binding via OBS WebSocket events (recording indicator, mute indicator, etc.).
- Per-key partial re-render on state change.

## Deferred to Phase 4

- Windows daemon (`sdac.platform._windows` currently raises NotImplementedError).
- Active-window watcher (Linux ewmh + Windows User32) for automatic profile switching.
