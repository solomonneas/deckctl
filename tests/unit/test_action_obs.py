from __future__ import annotations

from unittest.mock import patch

import deckctl.actions  # noqa: F401 - registers handlers
from deckctl.actions import get_handler
from deckctl.config import (
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
        return f"obsws://192.0.2.10:4455/{name}-pass"


def test_obs_scene_switch_shells_to_obs_cmd():
    action = ObsSceneSwitchAction(type="obs.scene.switch", host="studio", scene="Camera")
    with patch("deckctl.actions.obs.subprocess.run") as run:
        get_handler("obs.scene.switch").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://192.0.2.10:4455/studio-pass", "scene", "switch", "Camera"],
        check=True,
    )


def test_obs_recording_toggle_shells_to_obs_cmd():
    action = ObsRecordingToggleAction(type="obs.recording.toggle", host="studio")
    with patch("deckctl.actions.obs.subprocess.run") as run:
        get_handler("obs.recording.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://192.0.2.10:4455/studio-pass", "recording", "toggle"],
        check=True,
    )


def test_obs_streaming_toggle_shells_to_obs_cmd():
    action = ObsStreamingToggleAction(type="obs.streaming.toggle", host="studio")
    with patch("deckctl.actions.obs.subprocess.run") as run:
        get_handler("obs.streaming.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://192.0.2.10:4455/studio-pass", "streaming", "toggle"],
        check=True,
    )


def test_obs_replay_save_shells_to_obs_cmd():
    action = ObsReplaySaveAction(type="obs.replay.save", host="studio")
    with patch("deckctl.actions.obs.subprocess.run") as run:
        get_handler("obs.replay.save").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://192.0.2.10:4455/studio-pass", "replay", "save"],
        check=True,
    )


def test_obs_virtualcam_toggle_shells_to_obs_cmd():
    action = ObsVirtualCamToggleAction(type="obs.virtualcam.toggle", host="studio")
    with patch("deckctl.actions.obs.subprocess.run") as run:
        get_handler("obs.virtualcam.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://192.0.2.10:4455/studio-pass", "virtual-camera", "toggle"],
        check=True,
    )


def test_obs_input_mute_toggle_shells_to_obs_cmd():
    action = ObsInputMuteToggleAction(
        type="obs.input.mute.toggle", host="studio", input_name="Mic"
    )
    with patch("deckctl.actions.obs.subprocess.run") as run:
        get_handler("obs.input.mute.toggle").execute(action, _FakeCtx())
    run.assert_called_once_with(
        ["obs-cmd", "-w", "obsws://192.0.2.10:4455/studio-pass", "audio", "toggle", "Mic"],
        check=True,
    )
