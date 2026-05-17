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

    def execute(self, action: ObsSceneSwitchAction, ctx: DaemonContext) -> None:
        del action, ctx
        _not_yet("obs.scene.switch")


@register
class ObsRecordingToggleHandler:
    action_type: ClassVar[str] = "obs.recording.toggle"

    def execute(self, action: ObsRecordingToggleAction, ctx: DaemonContext) -> None:
        del action, ctx
        _not_yet("obs.recording.toggle")


@register
class ObsStreamingToggleHandler:
    action_type: ClassVar[str] = "obs.streaming.toggle"

    def execute(self, action: ObsStreamingToggleAction, ctx: DaemonContext) -> None:
        del action, ctx
        _not_yet("obs.streaming.toggle")


@register
class ObsReplaySaveHandler:
    action_type: ClassVar[str] = "obs.replay.save"

    def execute(self, action: ObsReplaySaveAction, ctx: DaemonContext) -> None:
        del action, ctx
        _not_yet("obs.replay.save")


@register
class ObsVirtualCamToggleHandler:
    action_type: ClassVar[str] = "obs.virtualcam.toggle"

    def execute(self, action: ObsVirtualCamToggleAction, ctx: DaemonContext) -> None:
        del action, ctx
        _not_yet("obs.virtualcam.toggle")


@register
class ObsInputMuteToggleHandler:
    action_type: ClassVar[str] = "obs.input.mute.toggle"

    def execute(self, action: ObsInputMuteToggleAction, ctx: DaemonContext) -> None:
        del action, ctx
        _not_yet("obs.input.mute.toggle")
