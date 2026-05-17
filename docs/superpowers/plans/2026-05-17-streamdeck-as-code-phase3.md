# streamdeck-as-code Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire OBS to the daemon so buttons can switch scenes / toggle recording / save replay / mute inputs over the LAN, AND so indicator-bound keys reflect live OBS state (red border on the REC key when OBS is actually recording).

**Architecture:** Action handlers stay synchronous and shell out to the existing `obs-cmd` binary on PATH (one subprocess per press; reuses the LAN auth wiring we built earlier in the day). A new `sdac.obs.OBSClient` connects to each `obs_hosts` entry via `obsws-python`'s sync `EventClient`, subscribes to six event types, and posts state changes through a callback the daemon installs. The daemon owns an `(bind_kind, host, qualifier) -> bool` state map; OBS callbacks update it under the daemon's RLock and trigger per-key re-renders for indicator-bound keys on the current page only. OBS reachability gets a new doctor check.

**Tech Stack:** Python 3.12, `obsws-python>=1.6` (sync EventClient for events + ReqClient for the reachability ping), `obs-cmd` already on PATH for action execution.

---

## Scope

**In Phase 3:**
- 6 OBS action handlers shell out to `obs-cmd` (replacing the `NotImplementedError` stubs).
- `OBSClient` class — wraps one obsws-python `EventClient` per host, subscribes to 6 events.
- `Daemon` owns an indicator state map; on OBS event → update map → re-render bound keys on current page.
- `Indicator` resolution: scene-current keys flip when the scene_name in the event matches `indicator.scene`; input-mute keys flip per `indicator.input_name`.
- `sdac doctor` adds a per-host OBS reachability check (`Severity.WARN` if unreachable, `Severity.PASS` if connected).
- Mocked tests (no live OBS instance required for CI).

**Out of scope (deferred to Phase 4):**
- Windows daemon, Windows-specific OBS reachability fallbacks.

**Out of scope (deferred to Phase 5):**
- pyproject polish, ClawHub publishing, GitHub push.

## File Structure

```
streamdeck-as-code/
  pyproject.toml                # Modify: add obsws-python dep
  src/sdac/
    obs/
      __init__.py               # NEW: re-exports
      client.py                 # NEW: OBSClient (per-host websocket subscription)
      url.py                    # NEW: parse obsws://host:port/password URLs
    actions/
      obs.py                    # Modify: replace stubs with real shell-outs
      base.py                   # Modify: extend DaemonContext for obs_url lookup
    daemon.py                   # Modify: indicator state map, OBSClient lifecycle, partial re-render
    doctor.py                   # Modify: add check_obs_reachability
    config.py                   # No change (Indicator + ObsHost already exist from Phase 1)
    cli.py                      # Modify: daemon command informs about OBS host failures
  tests/
    unit/
      test_obs_url.py           # NEW
      test_obs_client.py        # NEW
      test_action_obs.py        # NEW (replaces the previously-skipped stub paths)
      test_daemon_indicators.py # NEW
      test_doctor.py            # Modify: add reachability test
  docs/
    schema.md                   # Modify: remove the "obs.* handlers raise NotImplementedError" note
README.md                       # Modify: status block to Phase 3 + new OBS section
```

**Boundary contracts:**
- `sdac.obs.client.OBSClient` is the only module that imports `obsws_python`. Daemon and handlers don't.
- `sdac.obs.url.parse_obsws_url` is the single place URL parsing lives. Both `OBSClient` (events) and `actions/obs.py` (commands) use it.
- The DaemonContext gains exactly ONE new method: `obs_host_url(name) -> str`. Handlers don't poke into the daemon's config directly.

---

## Task 1: Add `obsws-python` dep + URL parser

**Files:**
- Modify: `pyproject.toml`
- Create: `src/sdac/obs/__init__.py`
- Create: `src/sdac/obs/url.py`
- Create: `tests/unit/test_obs_url.py`

- [ ] **Step 1: Add `obsws-python` to `[project] dependencies` in `pyproject.toml`**

In the existing dependencies list, append after `watchdog>=4.0`:

```toml
    "obsws-python>=1.6",
```

- [ ] **Step 2: Reinstall and verify import**

```bash
cd ~/repos/streamdeck-as-code
. .venv/bin/activate
pip install -e ".[dev]"
python -c "import obsws_python; print(obsws_python.__name__, 'ok')"
```

Expected: `obsws_python ok`.

- [ ] **Step 3: Create `src/sdac/obs/__init__.py`**

```python
"""OBS WebSocket subscription + URL parsing.

The action execution path (handlers in `sdac.actions.obs`) shells out to the
`obs-cmd` binary on PATH — this package is just for event subscription and
URL parsing.
"""

from sdac.obs.client import OBSClient, OBSConnectError, OBSEvent
from sdac.obs.url import ParsedObsws, parse_obsws_url

__all__ = ["OBSClient", "OBSConnectError", "OBSEvent", "ParsedObsws", "parse_obsws_url"]
```

- [ ] **Step 4: Write failing test — `tests/unit/test_obs_url.py`**

```python
from __future__ import annotations

import pytest

from sdac.obs.url import ParsedObsws, parse_obsws_url


def test_parse_full_url():
    p = parse_obsws_url("obsws://127.0.0.1:4455/secret123")
    assert p == ParsedObsws(host="127.0.0.1", port=4455, password="secret123")


def test_parse_url_without_password():
    p = parse_obsws_url("obsws://example.com:4455")
    assert p.host == "example.com"
    assert p.port == 4455
    assert p.password == ""


def test_parse_url_with_default_port_falls_back_to_4455():
    p = parse_obsws_url("obsws://host/abc")
    assert p.port == 4455
    assert p.password == "abc"


def test_parse_url_rejects_non_obsws_scheme():
    with pytest.raises(ValueError, match="obsws://"):
        parse_obsws_url("https://example.com/secret")


def test_parse_url_rejects_missing_host():
    with pytest.raises(ValueError, match="host"):
        parse_obsws_url("obsws://")
```

- [ ] **Step 5: Run failing**

```bash
pytest tests/unit/test_obs_url.py -v
```

Expected: ImportError on `sdac.obs.url`.

- [ ] **Step 6: Write `src/sdac/obs/url.py`**

```python
"""Parse `obsws://host:port/password` URLs.

This is the single source of truth for OBS URL parsing — both the event
client and the action handlers use it.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ParsedObsws:
    host: str
    port: int
    password: str


def parse_obsws_url(url: str) -> ParsedObsws:
    """Parse a URL of the shape `obsws://host[:port][/password]`.

    Defaults: port=4455, password="" (empty string).
    Raises ValueError if the scheme is not obsws:// or the host is missing.
    """
    parsed = urlparse(url)
    if parsed.scheme != "obsws":
        raise ValueError(f"expected obsws:// URL, got scheme {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("obsws URL missing host")
    port = parsed.port if parsed.port is not None else 4455
    password = parsed.path.lstrip("/") if parsed.path else ""
    return ParsedObsws(host=parsed.hostname, port=port, password=password)
```

(Note: we will create `client.py` in Task 2; the `__init__.py` imports from it will fail until then. That's fine — we run only the URL test in this task.)

- [ ] **Step 7: Run only the URL test**

```bash
pytest tests/unit/test_obs_url.py -v
```

Expected: 5 passing. (The `__init__.py` imports `OBSClient` etc., which don't exist yet — but the test imports directly from `sdac.obs.url`, bypassing the package's `__init__`. If the test fails with an `ImportError` from `__init__.py`, comment out the `from sdac.obs.client import ...` line in `__init__.py` temporarily and re-enable it in Task 2.)

- [ ] **Step 8: Make `__init__.py` import-safe before client.py exists**

Temporarily replace `src/sdac/obs/__init__.py` with:

```python
"""OBS WebSocket subscription + URL parsing.

The action execution path (handlers in `sdac.actions.obs`) shells out to the
`obs-cmd` binary on PATH — this package is just for event subscription and
URL parsing.
"""

from sdac.obs.url import ParsedObsws, parse_obsws_url

__all__ = ["ParsedObsws", "parse_obsws_url"]
```

Task 2 restores the full version once `client.py` exists.

- [ ] **Step 9: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 115 tests passing.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml src/sdac/obs/ tests/unit/test_obs_url.py
git commit -m "feat(obs): add obsws-python dep + URL parser"
```

---

## Task 2: `OBSClient` (per-host websocket event subscription)

**Files:**
- Create: `src/sdac/obs/client.py`
- Modify: `src/sdac/obs/__init__.py` (restore full exports)
- Create: `tests/unit/test_obs_client.py`

- [ ] **Step 1: Write failing test — `tests/unit/test_obs_client.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sdac.obs.client import OBSClient, OBSConnectError, OBSEvent


def test_obs_event_dataclass_holds_kind_qualifier_active():
    ev = OBSEvent(host="roc", kind="obs.recording.state", qualifier=None, active=True)
    assert ev.host == "roc"
    assert ev.kind == "obs.recording.state"
    assert ev.qualifier is None
    assert ev.active is True


def test_obs_client_constructor_does_not_connect():
    """Constructing OBSClient with a callback is cheap; .start() opens the socket."""
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    assert not c.is_connected


def test_obs_client_start_calls_event_client_constructor_with_parsed_url():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/secret", on_event=cb)
    with patch("obsws_python.EventClient") as ec:
        c.start()
    ec.assert_called_once()
    kwargs = ec.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 4455
    assert kwargs["password"] == "secret"
    assert c.is_connected


def test_obs_client_start_raises_obs_connect_error_on_failure():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    with patch("obsws_python.EventClient", side_effect=OSError("connection refused")):
        with pytest.raises(OBSConnectError, match="connection refused"):
            c.start()
    assert not c.is_connected


def test_obs_client_stop_disconnects():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/secret", on_event=cb)
    fake_event_client = MagicMock()
    with patch("obsws_python.EventClient", return_value=fake_event_client):
        c.start()
    c.stop()
    fake_event_client.disconnect.assert_called_once()
    assert not c.is_connected


def test_obs_client_translates_record_state_changed_event_to_callback():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    # Simulate the event arrival without involving real obsws-python
    data = MagicMock()
    data.output_state = "OBS_WEBSOCKET_OUTPUT_STARTED"
    c._on_record_state_changed(data)
    cb.assert_called_once()
    ev = cb.call_args.args[0]
    assert isinstance(ev, OBSEvent)
    assert ev.host == "roc"
    assert ev.kind == "obs.recording.state"
    assert ev.active is True


def test_obs_client_translates_record_state_stopped_event_to_inactive():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.output_state = "OBS_WEBSOCKET_OUTPUT_STOPPED"
    c._on_record_state_changed(data)
    ev = cb.call_args.args[0]
    assert ev.active is False


def test_obs_client_translates_scene_change():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.scene_name = "Camera"
    c._on_current_program_scene_changed(data)
    ev = cb.call_args.args[0]
    assert ev.kind == "obs.scene.current"
    assert ev.qualifier == "Camera"
    assert ev.active is True


def test_obs_client_translates_input_mute_state():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.input_name = "Mic"
    data.input_muted = True
    c._on_input_mute_state_changed(data)
    ev = cb.call_args.args[0]
    assert ev.kind == "obs.input.muted"
    assert ev.qualifier == "Mic"
    assert ev.active is True
```

- [ ] **Step 2: Run failing**

```bash
. .venv/bin/activate
pytest tests/unit/test_obs_client.py -v
```

Expected: ImportError on `sdac.obs.client`.

- [ ] **Step 3: Write `src/sdac/obs/client.py`**

```python
"""Per-host OBS WebSocket subscription.

Wraps obsws-python's sync EventClient. On each subscribed event, translates
the obs-websocket payload to a uniform `OBSEvent` and invokes the user's
`on_event` callback. Callbacks fire on the event client's worker thread.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import obsws_python  # type: ignore[import-untyped]

from sdac.errors import SdacError
from sdac.obs.url import parse_obsws_url

log = logging.getLogger(__name__)


class OBSConnectError(SdacError):
    """Raised when OBSClient.start() cannot reach the configured host."""


@dataclass(frozen=True)
class OBSEvent:
    """A normalized OBS state change.

    `kind` is one of:
      obs.recording.state, obs.streaming.state, obs.replay.state,
      obs.virtualcam.state, obs.scene.current, obs.input.muted
    `qualifier` is the scene name (for obs.scene.current) or the input name
    (for obs.input.muted); None for output-state events.
    `active` is the boolean "is this state on right now?"
    """

    host: str
    kind: str
    qualifier: str | None
    active: bool


_ACTIVE_OUTPUT_STATES = {
    "OBS_WEBSOCKET_OUTPUT_STARTED",
    "OBS_WEBSOCKET_OUTPUT_STARTING",
}


class OBSClient:
    """Wraps a single obsws-python EventClient for one OBS host."""

    def __init__(self, *, host: str, url: str, on_event: Callable[[OBSEvent], None]) -> None:
        self._host = host
        self._url = url
        self._on_event = on_event
        self._ec: Any | None = None

    @property
    def is_connected(self) -> bool:
        return self._ec is not None

    @property
    def host(self) -> str:
        return self._host

    def start(self) -> None:
        if self._ec is not None:
            return
        parsed = parse_obsws_url(self._url)
        try:
            self._ec = obsws_python.EventClient(
                host=parsed.host,
                port=parsed.port,
                password=parsed.password,
                subs=obsws_python.Subs.LOW_VOLUME,
            )
        except Exception as e:
            raise OBSConnectError(f"OBS {self._host} ({self._url}): {e}") from e
        ec = self._ec
        ec.callback.register(self._on_record_state_changed)
        ec.callback.register(self._on_stream_state_changed)
        ec.callback.register(self._on_replay_buffer_state_changed)
        ec.callback.register(self._on_virtualcam_state_changed)
        ec.callback.register(self._on_current_program_scene_changed)
        ec.callback.register(self._on_input_mute_state_changed)
        log.info("OBS %s connected (%s:%d)", self._host, parsed.host, parsed.port)

    def stop(self) -> None:
        if self._ec is None:
            return
        try:
            self._ec.disconnect()
        except Exception:
            log.exception("OBS %s: error during disconnect", self._host)
        finally:
            self._ec = None

    # ---- obsws-python callbacks (sync, fire on event client thread) ----

    def _on_record_state_changed(self, data: Any) -> None:
        self._on_event(OBSEvent(
            host=self._host,
            kind="obs.recording.state",
            qualifier=None,
            active=getattr(data, "output_state", "") in _ACTIVE_OUTPUT_STATES,
        ))

    def _on_stream_state_changed(self, data: Any) -> None:
        self._on_event(OBSEvent(
            host=self._host,
            kind="obs.streaming.state",
            qualifier=None,
            active=getattr(data, "output_state", "") in _ACTIVE_OUTPUT_STATES,
        ))

    def _on_replay_buffer_state_changed(self, data: Any) -> None:
        self._on_event(OBSEvent(
            host=self._host,
            kind="obs.replay.state",
            qualifier=None,
            active=getattr(data, "output_state", "") in _ACTIVE_OUTPUT_STATES,
        ))

    def _on_virtualcam_state_changed(self, data: Any) -> None:
        self._on_event(OBSEvent(
            host=self._host,
            kind="obs.virtualcam.state",
            qualifier=None,
            active=getattr(data, "output_state", "") in _ACTIVE_OUTPUT_STATES,
        ))

    def _on_current_program_scene_changed(self, data: Any) -> None:
        self._on_event(OBSEvent(
            host=self._host,
            kind="obs.scene.current",
            qualifier=getattr(data, "scene_name", None),
            active=True,
        ))

    def _on_input_mute_state_changed(self, data: Any) -> None:
        self._on_event(OBSEvent(
            host=self._host,
            kind="obs.input.muted",
            qualifier=getattr(data, "input_name", None),
            active=bool(getattr(data, "input_muted", False)),
        ))
```

- [ ] **Step 4: Restore the full `src/sdac/obs/__init__.py`**

```python
"""OBS WebSocket subscription + URL parsing."""

from sdac.obs.client import OBSClient, OBSConnectError, OBSEvent
from sdac.obs.url import ParsedObsws, parse_obsws_url

__all__ = ["OBSClient", "OBSConnectError", "OBSEvent", "ParsedObsws", "parse_obsws_url"]
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_obs_client.py -v
```

Expected: 9 passing.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 124 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/obs/client.py src/sdac/obs/__init__.py tests/unit/test_obs_client.py
git commit -m "feat(obs): OBSClient — per-host websocket event subscription"
```

---

## Task 3: DaemonContext extension + OBS action handlers

**Files:**
- Modify: `src/sdac/actions/base.py`
- Modify: `src/sdac/actions/obs.py` (replace stubs with real shell-outs)
- Modify: `tests/unit/test_action_compound.py` and `tests/unit/test_action_navigation.py` and any test that defines a `_NullCtx` / `_RecordingCtx` — they need the new method
- Create: `tests/unit/test_action_obs.py`

- [ ] **Step 1: Extend `DaemonContext` Protocol in `src/sdac/actions/base.py`**

Replace the body of `DaemonContext` with:

```python
@runtime_checkable
class DaemonContext(Protocol):
    """The subset of the daemon that action handlers are allowed to call."""

    def switch_page(self, name: str) -> None: ...

    def switch_profile(self, name: str) -> None: ...

    def obs_host_url(self, name: str) -> str: ...
```

- [ ] **Step 2: Update every test `_NullCtx` / `_FakeCtx` / `_RecordingCtx` to satisfy the new method**

For each of the following test files, find the existing test-only context class and add this method:

```python
    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")
```

Files to patch (search for the class definitions):
- `tests/unit/test_action_shell.py` — `_NullCtx`
- `tests/unit/test_action_keys.py` — `_NullCtx`
- `tests/unit/test_action_opening.py` — `_NullCtx`
- `tests/unit/test_action_system_audio.py` — `_NullCtx`
- `tests/unit/test_action_compound.py` — `_NullCtx`
- `tests/unit/test_action_navigation.py` — `_RecordingCtx`
- `tests/unit/test_actions_registry.py` — `_FakeCtx`

(The `_RecordingCtx` in `test_action_navigation.py` keeps its existing `pages`/`profiles` recording; just add the obs method.)

- [ ] **Step 3: Run all action tests + registry test to confirm protocol compliance**

```bash
. .venv/bin/activate
pytest tests/unit/test_action_shell.py tests/unit/test_action_keys.py \
       tests/unit/test_action_opening.py tests/unit/test_action_system_audio.py \
       tests/unit/test_action_compound.py tests/unit/test_action_navigation.py \
       tests/unit/test_actions_registry.py -v
```

Expected: all passing.

- [ ] **Step 4: Write failing tests — `tests/unit/test_action_obs.py`**

```python
from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401 — registers handlers
from sdac.actions import get_handler
from sdac.config import (
    ObsInputMuteToggleAction,
    ObsRecordingToggleAction,
    ObsReplaySaveAction,
    ObsSceneSwitchAction,
    ObsStreamingToggleAction,
    ObsVirtualCamToggleAction,
)


class _FakeCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...

    def obs_host_url(self, name: str) -> str:
        return f"obsws://127.0.0.1:4455/{name}-pass"


def test_obs_scene_switch_shells_to_obs_cmd():
    action = ObsSceneSwitchAction(type="obs.scene.switch", host="roc", scene="Camera")
    with patch("sdac.actions.obs.subprocess.run") as run:
        get_handler("obs.scene.switch").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://127.0.0.1:4455/roc-pass", "scene", "switch", "Camera"],
        check=True,
    )


def test_obs_recording_toggle_shells_to_obs_cmd():
    action = ObsRecordingToggleAction(type="obs.recording.toggle", host="roc")
    with patch("sdac.actions.obs.subprocess.run") as run:
        get_handler("obs.recording.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://127.0.0.1:4455/roc-pass", "recording", "toggle"],
        check=True,
    )


def test_obs_streaming_toggle_shells_to_obs_cmd():
    action = ObsStreamingToggleAction(type="obs.streaming.toggle", host="roc")
    with patch("sdac.actions.obs.subprocess.run") as run:
        get_handler("obs.streaming.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://127.0.0.1:4455/roc-pass", "streaming", "toggle"],
        check=True,
    )


def test_obs_replay_save_shells_to_obs_cmd():
    action = ObsReplaySaveAction(type="obs.replay.save", host="roc")
    with patch("sdac.actions.obs.subprocess.run") as run:
        get_handler("obs.replay.save").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://127.0.0.1:4455/roc-pass", "replay", "save"],
        check=True,
    )


def test_obs_virtualcam_toggle_shells_to_obs_cmd():
    action = ObsVirtualCamToggleAction(type="obs.virtualcam.toggle", host="roc")
    with patch("sdac.actions.obs.subprocess.run") as run:
        get_handler("obs.virtualcam.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://127.0.0.1:4455/roc-pass", "virtual-camera", "toggle"],
        check=True,
    )


def test_obs_input_mute_toggle_shells_to_obs_cmd():
    action = ObsInputMuteToggleAction(
        type="obs.input.mute.toggle", host="roc", input_name="Mic"
    )
    with patch("sdac.actions.obs.subprocess.run") as run:
        get_handler("obs.input.mute.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://127.0.0.1:4455/roc-pass", "audio", "toggle-mute", "Mic"],
        check=True,
    )
```

- [ ] **Step 5: Replace the stub body of `src/sdac/actions/obs.py` with real implementations**

```python
"""OBS action handlers.

Each handler shells out to the `obs-cmd` binary on PATH (the same one used by
the obs-ctl wrapper). The handler resolves the host name → URL via the
DaemonContext.
"""

from __future__ import annotations

import subprocess
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


def _obs_cmd(url: str, *args: str) -> None:
    subprocess.run(["obs-cmd", "-w", url, *args], check=True)


@register
class ObsSceneSwitchHandler:
    action_type: ClassVar[str] = "obs.scene.switch"

    def execute(self, action: ObsSceneSwitchAction, ctx: DaemonContext) -> None:
        _obs_cmd(ctx.obs_host_url(action.host), "scene", "switch", action.scene)


@register
class ObsRecordingToggleHandler:
    action_type: ClassVar[str] = "obs.recording.toggle"

    def execute(self, action: ObsRecordingToggleAction, ctx: DaemonContext) -> None:
        _obs_cmd(ctx.obs_host_url(action.host), "recording", "toggle")


@register
class ObsStreamingToggleHandler:
    action_type: ClassVar[str] = "obs.streaming.toggle"

    def execute(self, action: ObsStreamingToggleAction, ctx: DaemonContext) -> None:
        _obs_cmd(ctx.obs_host_url(action.host), "streaming", "toggle")


@register
class ObsReplaySaveHandler:
    action_type: ClassVar[str] = "obs.replay.save"

    def execute(self, action: ObsReplaySaveAction, ctx: DaemonContext) -> None:
        _obs_cmd(ctx.obs_host_url(action.host), "replay", "save")


@register
class ObsVirtualCamToggleHandler:
    action_type: ClassVar[str] = "obs.virtualcam.toggle"

    def execute(self, action: ObsVirtualCamToggleAction, ctx: DaemonContext) -> None:
        _obs_cmd(ctx.obs_host_url(action.host), "virtual-camera", "toggle")


@register
class ObsInputMuteToggleHandler:
    action_type: ClassVar[str] = "obs.input.mute.toggle"

    def execute(self, action: ObsInputMuteToggleAction, ctx: DaemonContext) -> None:
        _obs_cmd(ctx.obs_host_url(action.host), "audio", "toggle-mute", action.input_name)
```

- [ ] **Step 6: Run new OBS action tests**

```bash
pytest tests/unit/test_action_obs.py -v
```

Expected: 6 passing.

- [ ] **Step 7: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 130 tests passing.

- [ ] **Step 8: Commit**

```bash
git add src/sdac/actions/base.py src/sdac/actions/obs.py tests/unit/test_action_obs.py \
        tests/unit/test_action_*.py tests/unit/test_actions_registry.py
git commit -m "feat(actions): real OBS handlers shell out to obs-cmd; ctx.obs_host_url()"
```

---

## Task 4: Daemon integration — obs_host_url + indicator state map

**Files:**
- Modify: `src/sdac/daemon.py`
- Create: `tests/unit/test_daemon_indicators.py`

- [ ] **Step 1: Add the `obs_host_url` method to `Daemon`**

In `src/sdac/daemon.py`, after the existing `switch_profile` method, add:

```python
    def obs_host_url(self, name: str) -> str:
        with self._lock:
            assert self._config is not None
            if name not in self._config.obs_hosts:
                raise KeyError(f"unknown obs host: {name}")
            return self._config.obs_hosts[name].url
```

- [ ] **Step 2: Add the indicator state map + helpers**

Near the top of `Daemon.__init__`, add this attribute:

```python
        self._indicator_state: dict[tuple[str, str, str | None], bool] = {}
```

Then add these methods to `Daemon` (anywhere after `obs_host_url`):

```python
    def _indicator_active(self, ind: "Indicator") -> bool:
        """Look up the current cached state for an indicator binding."""
        if ind.bind == "obs.scene.current":
            qualifier = ind.scene
        elif ind.bind == "obs.input.muted":
            qualifier = ind.input_name
        else:
            qualifier = None
        return self._indicator_state.get((ind.bind, ind.host, qualifier), False)

    def _update_indicator(self, bind_kind: str, host: str, qualifier: str | None, active: bool) -> list[int]:
        """Update the state map and return the keys on the current page that need re-rendering."""
        with self._lock:
            key = (bind_kind, host, qualifier)
            prev = self._indicator_state.get(key)
            self._indicator_state[key] = active
            if prev == active:
                return []
            if (
                self._config is None
                or self._current_profile is None
                or self._current_page is None
            ):
                return []
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            affected: list[int] = []
            for idx, k in page.keys.items():
                if k.indicator is None:
                    continue
                ind = k.indicator
                if ind.bind != bind_kind or ind.host != host:
                    continue
                # Scene/input bindings only fire for matching qualifier; output-state for all.
                if ind.bind == "obs.scene.current" and ind.scene != qualifier:
                    # If the active scene changed, also mark this binding's prior "active=True" key as inactive.
                    # We achieve this by always recording state per scene_name; the lookup uses ind.scene.
                    pass
                elif ind.bind == "obs.input.muted" and ind.input_name != qualifier:
                    continue
                affected.append(idx)
            return affected
```

Note on `obs.scene.current` handling: each scene gets its own state map entry, keyed by scene_name. When a SceneChanged event arrives with `scene_name="Camera"`, we set `("obs.scene.current", host, "Camera")` to True. We DO NOT automatically zero out the previously-active scene's entry — but we also re-render every scene-bound key on the page. That works because `_indicator_active` checks the bound scene's specific entry, which is True only for the currently-active scene.

Actually that won't work — we never set the previously-active scene to False. So if we switch from "Camera" to "Lobby", the "Camera" binding stays True. Fix: when a scene-current event arrives, sweep all keys on the page with `obs.scene.current` bindings on this host and zero them out before setting the new one.

Adjust the implementation: `obs.scene.current` handling must clear the state map for ALL `(obs.scene.current, host, *)` keys before setting the new one.

Update the helper:

```python
    def _update_indicator(self, bind_kind: str, host: str, qualifier: str | None, active: bool) -> list[int]:
        """Update the state map and return the keys on the current page that need re-rendering."""
        with self._lock:
            if bind_kind == "obs.scene.current":
                # Scene change: zero out all other scenes on this host so previously-active key flips off.
                affected_pre: list[int] = []
                for k_state in list(self._indicator_state):
                    bk, h, _q = k_state
                    if bk == "obs.scene.current" and h == host:
                        self._indicator_state[k_state] = False
                # Set the new active scene
                self._indicator_state[(bind_kind, host, qualifier)] = active
            else:
                key = (bind_kind, host, qualifier)
                prev = self._indicator_state.get(key)
                self._indicator_state[key] = active
                if prev == active:
                    return []
            # Compute affected keys
            if (
                self._config is None
                or self._current_profile is None
                or self._current_page is None
            ):
                return []
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            affected: list[int] = []
            for idx, k in page.keys.items():
                if k.indicator is None:
                    continue
                ind = k.indicator
                if ind.bind != bind_kind or ind.host != host:
                    continue
                if ind.bind == "obs.input.muted" and ind.input_name != qualifier:
                    continue
                affected.append(idx)
            return affected
```

Also import `Indicator` at the top of `daemon.py`:

```python
from sdac.config import Config, Indicator, load_config
```

- [ ] **Step 3: Add a per-key re-render helper to `Daemon`**

```python
    def _rerender_keys(self, indices: list[int]) -> None:
        """Re-render specific keys without touching the rest of the page."""
        with self._lock:
            assert self._config is not None
            assert self._current_profile is not None
            assert self._current_page is not None
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            keys = {i: page.keys.get(i) for i in indices}
        if not self._device.is_open:
            return
        for idx, k in keys.items():
            if k is None:
                continue
            state = "active" if (k.indicator and self._indicator_active(k.indicator)) else "idle"
            try:
                img = render_key(k, state=state)
                self._device.set_key_image(idx, img)
            except Exception:
                log.exception("indicator re-render failed on key %d", idx)
```

- [ ] **Step 4: Update `render_current_page` to honor indicator state for full renders too**

Find the inner loop in `render_current_page`:

```python
            if idx in keys:
                img = render_key(keys[idx], state="idle")
            else:
                img = blank
```

Replace with:

```python
            if idx in keys:
                k = keys[idx]
                state = "active" if (k.indicator and self._indicator_active(k.indicator)) else "idle"
                img = render_key(k, state=state)
            else:
                img = blank
```

- [ ] **Step 5: Add the `on_obs_event` entry point for OBSClient callbacks**

Append this method to `Daemon`:

```python
    def on_obs_event(self, event: "OBSEvent") -> None:
        """Callback invoked by OBSClient when an event arrives on its worker thread."""
        affected = self._update_indicator(event.kind, event.host, event.qualifier, event.active)
        if affected:
            self._rerender_keys(affected)
```

Import `OBSEvent` at the top:

```python
from sdac.obs.client import OBSEvent
```

- [ ] **Step 6: Write failing tests — `tests/unit/test_daemon_indicators.py`**

```python
from __future__ import annotations

from pathlib import Path

import sdac.actions  # noqa: F401
from sdac.daemon import Daemon
from sdac.device import MockDevice
from sdac.obs.client import OBSEvent

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_indicator_active_initially_false():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    # streaming/home/key 1 has indicator bind=obs.recording.state host=roc
    rec_key = d._config.profiles["streaming"].pages["home"].keys[1]
    assert d._indicator_active(rec_key.indicator) is False


def test_on_obs_event_updates_state_map():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    d.switch_profile("streaming")
    device.images_pushed.clear()
    d.on_obs_event(OBSEvent(
        host="roc", kind="obs.recording.state", qualifier=None, active=True,
    ))
    rec_key = d._config.profiles["streaming"].pages["home"].keys[1]
    assert d._indicator_active(rec_key.indicator) is True
    # Key 1 should have been re-rendered (no full page repush)
    assert set(device.images_pushed.keys()) == {1}


def test_obs_event_for_other_host_does_not_trigger_render():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.switch_profile("streaming")
    device.images_pushed.clear()
    d.on_obs_event(OBSEvent(
        host="windows-host", kind="obs.recording.state", qualifier=None, active=True,
    ))
    assert device.images_pushed == {}


def test_obs_scene_change_flips_previously_active():
    """When the active scene changes, the previous scene's binding goes inactive."""
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.switch_profile("streaming")
    # First, mark Camera scene active
    d.on_obs_event(OBSEvent(host="roc", kind="obs.scene.current", qualifier="Camera", active=True))
    assert d._indicator_state.get(("obs.scene.current", "roc", "Camera")) is True
    # Now switch to a different scene
    d.on_obs_event(OBSEvent(host="roc", kind="obs.scene.current", qualifier="Lobby", active=True))
    assert d._indicator_state[("obs.scene.current", "roc", "Camera")] is False
    assert d._indicator_state[("obs.scene.current", "roc", "Lobby")] is True


def test_obs_event_with_no_change_is_noop():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.switch_profile("streaming")
    # First event sets True
    d.on_obs_event(OBSEvent(host="roc", kind="obs.recording.state", qualifier=None, active=True))
    device.images_pushed.clear()
    # Second identical event should not re-render
    d.on_obs_event(OBSEvent(host="roc", kind="obs.recording.state", qualifier=None, active=True))
    assert device.images_pushed == {}


def test_obs_host_url_lookup():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "env_var.yaml")
    import os
    os.environ["SDAC_TEST_OBS_PASS"] = "letmein"
    d.load()
    url = d.obs_host_url("roc")
    assert url == "obsws://127.0.0.1:4455/letmein"


def test_obs_host_url_unknown_raises():
    import pytest
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    with pytest.raises(KeyError, match="unknown obs host"):
        d.obs_host_url("ghost")
```

- [ ] **Step 7: Run failing**

```bash
pytest tests/unit/test_daemon_indicators.py -v
```

Expected: most tests fail (until daemon methods exist).

- [ ] **Step 8: Run after implementation**

```bash
pytest tests/unit/test_daemon_indicators.py -v
```

Expected: 7 passing.

- [ ] **Step 9: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 137 tests passing.

- [ ] **Step 10: Commit**

```bash
git add src/sdac/daemon.py tests/unit/test_daemon_indicators.py
git commit -m "feat(daemon): indicator state map + per-key re-render on OBS event"
```

---

## Task 5: Daemon OBSClient lifecycle

**Files:**
- Modify: `src/sdac/daemon.py`
- Modify: `tests/unit/test_daemon.py` (add lifecycle test using mocked OBSClient)

- [ ] **Step 1: Add OBSClient management to `Daemon`**

Import at the top:

```python
from sdac.obs.client import OBSClient, OBSConnectError
```

In `__init__`, add:

```python
        self._obs_clients: list[OBSClient] = []
```

Add this method:

```python
    def start_obs_clients(self) -> None:
        """Open a websocket connection to each configured obs_host. Best-effort."""
        with self._lock:
            assert self._config is not None
            hosts = list(self._config.obs_hosts.items())
        for name, host in hosts:
            client = OBSClient(host=name, url=host.url, on_event=self.on_obs_event)
            try:
                client.start()
            except OBSConnectError as e:
                log.warning("OBS host %s unreachable: %s", name, e)
                continue
            self._obs_clients.append(client)
            log.info("OBS host %s subscribed for events", name)

    def stop_obs_clients(self) -> None:
        for c in self._obs_clients:
            c.stop()
        self._obs_clients.clear()
```

Update `run_forever` to call these. In the existing `run_forever`, replace the `try:` block opening with:

```python
        self.start_obs_clients()
        try:
            while not stop.is_set():
                stop.wait(timeout=1.0)
        finally:
            self.stop_obs_clients()
            self.stop_watching()
            if self._device.is_open:
                self._device.close()
```

- [ ] **Step 2: Write failing tests — append to `tests/unit/test_daemon.py`**

```python
def test_daemon_start_obs_clients_skips_unreachable(monkeypatch: pytest.MonkeyPatch):
    """A host that won't connect just gets logged; daemon continues."""
    from unittest.mock import MagicMock, patch

    from sdac.obs.client import OBSConnectError

    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "abc")
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "env_var.yaml")
    d.load()

    with patch("sdac.daemon.OBSClient") as oc:
        instance = MagicMock()
        instance.start.side_effect = OBSConnectError("nope")
        oc.return_value = instance
        d.start_obs_clients()
    assert d._obs_clients == []  # nothing was kept since start() failed


def test_daemon_start_obs_clients_keeps_successful_ones(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import MagicMock, patch
    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "abc")
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "env_var.yaml")
    d.load()
    with patch("sdac.daemon.OBSClient") as oc:
        instance = MagicMock()
        instance.start.return_value = None
        oc.return_value = instance
        d.start_obs_clients()
    assert len(d._obs_clients) == 1
    d.stop_obs_clients()
    instance.stop.assert_called_once()
```

- [ ] **Step 3: Run failing**

```bash
pytest tests/unit/test_daemon.py -k obs_clients -v
```

Expected: failing until methods exist.

- [ ] **Step 4: Run after implementation**

```bash
pytest tests/unit/test_daemon.py -k obs_clients -v
```

Expected: 2 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 139 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/daemon.py tests/unit/test_daemon.py
git commit -m "feat(daemon): OBS client lifecycle (best-effort connect per host)"
```

---

## Task 6: Doctor OBS reachability check

**Files:**
- Modify: `src/sdac/doctor.py`
- Modify: `tests/unit/test_doctor.py`

- [ ] **Step 1: Add the check function**

In `src/sdac/doctor.py`, add this function:

```python
def check_obs_reachability(config_path: str | None) -> CheckResult:
    """For each configured obs_hosts entry, attempt a quick connect via ReqClient."""
    if config_path is None:
        return CheckResult("obs_hosts", Severity.WARN, "skipped - no --config provided")
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        return CheckResult("obs_hosts", Severity.WARN, f"config error blocked OBS check: {e}")
    if not cfg.obs_hosts:
        return CheckResult("obs_hosts", Severity.PASS, "no obs_hosts configured")
    import obsws_python  # type: ignore[import-untyped]
    from sdac.obs.url import parse_obsws_url
    reachable: list[str] = []
    unreachable: list[str] = []
    for name, host in cfg.obs_hosts.items():
        try:
            parsed = parse_obsws_url(host.url)
            req = obsws_python.ReqClient(
                host=parsed.host, port=parsed.port, password=parsed.password, timeout=2,
            )
            req.disconnect()
            reachable.append(name)
        except Exception:
            unreachable.append(name)
    if unreachable:
        return CheckResult(
            "obs_hosts",
            Severity.WARN,
            f"reachable: {', '.join(reachable) or 'none'}; unreachable: {', '.join(unreachable)}",
        )
    return CheckResult("obs_hosts", Severity.PASS, f"reachable: {', '.join(reachable)}")
```

Add it to `run_all_checks` (append to the list, after `check_config(config_path)`):

```python
def run_all_checks(*, config_path: str | None) -> list[CheckResult]:
    return [
        check_libhidapi(),
        check_stream_deck(),
        check_python_deps(),
        check_system_binaries(),
        check_udev_rule(),
        check_service_status(),
        check_config(config_path),
        check_obs_reachability(config_path),
    ]
```

- [ ] **Step 2: Write failing tests — append to `tests/unit/test_doctor.py`**

```python
def test_check_obs_reachability_warn_without_config():
    from sdac.doctor import check_obs_reachability
    r = check_obs_reachability(None)
    assert r.severity is Severity.WARN


def test_check_obs_reachability_no_hosts_in_config_passes(tmp_path):
    from sdac.doctor import check_obs_reachability
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\nprofiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    r = check_obs_reachability(str(cfg))
    assert r.severity is Severity.PASS
    assert "no obs_hosts" in r.message.lower()


def test_check_obs_reachability_warn_on_unreachable(tmp_path, monkeypatch):
    from sdac.doctor import check_obs_reachability
    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "x")
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\n"
        "obs_hosts:\n"
        "  ghost:\n    url: obsws://127.0.0.1:6666/${SDAC_TEST_OBS_PASS}\n"
        "profiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    r = check_obs_reachability(str(cfg))
    # Port 6666 is unlikely to have OBS running on it.
    assert r.severity is Severity.WARN
    assert "ghost" in r.message
```

- [ ] **Step 3: Run failing**

```bash
. .venv/bin/activate
pytest tests/unit/test_doctor.py -k obs_reachability -v
```

Expected: ImportError on `check_obs_reachability`.

- [ ] **Step 4: Run after implementation**

```bash
pytest tests/unit/test_doctor.py -k obs_reachability -v
```

Expected: 3 passing. The third test may actually pass for a different reason (config validation fails because env var lookup or similar) — that's fine as long as severity is WARN.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 142 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/doctor.py tests/unit/test_doctor.py
git commit -m "feat(doctor): obs_hosts reachability check"
```

---

## Task 7: README + schema doc updates

**Files:**
- Modify: `README.md`
- Modify: `docs/schema.md`

- [ ] **Step 1: Update the README status block**

Replace the existing `**Status:** Phase 2b...` paragraph with:

```markdown
**Status:** Phase 3 (current). `sdac daemon` runs against a real Stream Deck MK.2; all 21 action types execute including OBS scene/recording/streaming/replay/virtualcam/input-mute controls over the LAN; indicator-bound keys reflect live OBS state. `sdac install-service` registers a systemd user unit + udev rule. `sdac doctor` reports device + deps + config + service + OBS reachability. Windows port lands in Phase 4.
```

- [ ] **Step 2: Update `## Capabilities` heading + bullets**

Replace with:

```markdown
## Capabilities (Phase 1 + 2a + 2b + 3)

- Validate a YAML config against the full v1 schema (Pydantic 2 discriminated union over 21 action types).
- Resolve `${ENV_VAR}` in any string field — keep passwords out of the YAML.
- Render every key in a profile/page as a single mosaic PNG (offline preview, no device required).
- Warn (or strict-reject with `--strict-perms`) when the config file is world-readable on POSIX.
- Run a daemon that owns a real Stream Deck MK.2 over USB and dispatches button presses to handlers.
- Hot-reload the config without restarting the daemon.
- Execute OBS actions over the LAN: scene switch, recording/streaming/replay/virtualcam toggle, audio mute.
- Live state indicators: keys bound to OBS recording/streaming/replay/scene/mute auto-update when OBS state changes.
- Install as a systemd user unit with one command (`sdac install-service`). Daemon autostarts at login.
- `sdac doctor` reports on device, deps, service status, config, and OBS reachability — exits non-zero on any FAIL.
```

- [ ] **Step 3: Add a new OBS section**

After the existing `## Install as a service (Phase 2b, Linux)` section, insert:

```markdown
## OBS integration (Phase 3)

Configure one or more OBS instances under `obs_hosts:` in your config, then any `obs.*` action can target them by name:

```yaml
obs_hosts:
  roc:
    url: obsws://127.0.0.1:4455/${OBS_ROC_PASS}
  windows-host:
    url: obsws://192.168.x.y:4455/${OBS_windows-host_PASS}

profiles:
  streaming:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Cam", bg: "#1e88e5"}
            action: {type: obs.scene.switch, host: roc, scene: "Camera"}
          1:
            icon:
              text: "REC"
              bg_idle: "#424242"
              bg_active: "#d32f2f"
            indicator: {bind: obs.recording.state, host: roc}
            action: {type: obs.recording.toggle, host: roc}
```

Actions execute via `obs-cmd` on PATH. The daemon also opens a WebSocket connection to each `obs_hosts` entry on startup to subscribe to state events; the REC key above turns red when OBS is actually recording, and back to gray when it stops. Hosts that aren't reachable at daemon startup are logged and skipped — actions targeting them will simply fail at dispatch time.

Indicators support:
- `obs.recording.state`, `obs.streaming.state`, `obs.replay.state`, `obs.virtualcam.state` — boolean output states
- `obs.scene.current` — match a `scene:` name; key is active when that scene is the current program scene
- `obs.input.muted` — match an `input_name:`; key is active when that audio input is muted
```

- [ ] **Step 4: Update `docs/schema.md`**

Find the "Phase 2a runtime note" paragraph (added in Phase 2a's docs) and replace it with:

```markdown
**Phase 3 runtime note:** all 21 action types execute. OBS actions (`obs.*`) shell out to `obs-cmd` on PATH and target the host named in the action. Indicators bound to OBS state are updated live via a WebSocket subscription to each configured `obs_hosts` entry.
```

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/schema.md
git commit -m "docs: Phase 3 — OBS execution + live indicators section"
```

---

## Done criteria for Phase 3

1. All 21 action types execute. The 6 OBS handlers shell out to `obs-cmd` with the correct argv.
2. Daemon opens a websocket subscription to each `obs_hosts` entry; unreachable hosts log + continue.
3. Indicator-bound keys re-render when OBS state changes — verified by the daemon_indicators tests using OBSEvent inputs against MockDevice.
4. `sdac doctor` reports OBS reachability with a PASS/WARN row.
5. Tests: 142+ passing. ruff + mypy clean.

## Out of scope (Phase 4)

- Windows daemon, OBS websocket on Windows.
- Active-window watcher.
- Multi-device.

## Out of scope (Phase 5)

- pyproject polish, GitHub push, ClawHub publish.
