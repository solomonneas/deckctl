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
