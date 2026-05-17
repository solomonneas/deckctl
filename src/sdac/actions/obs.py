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
        _obs_cmd(ctx.obs_host_url(action.host), "audio", "toggle", action.input_name)
