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

    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")


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
