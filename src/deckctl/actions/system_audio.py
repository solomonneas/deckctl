"""System volume and media-key actions."""

from __future__ import annotations

from typing import ClassVar

from deckctl.actions import register
from deckctl.actions.base import DaemonContext
from deckctl.config import (
    MediaNextAction,
    MediaPauseAction,
    MediaPlayAction,
    MediaPrevAction,
    SystemVolumeDownAction,
    SystemVolumeMuteAction,
    SystemVolumeUpAction,
)
from deckctl.platform import (
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

    def execute(self, action: SystemVolumeUpAction, ctx: DaemonContext) -> None:
        del ctx
        volume_up(step=action.step)


@register
class SystemVolumeDownHandler:
    action_type: ClassVar[str] = "system.volume.down"

    def execute(self, action: SystemVolumeDownAction, ctx: DaemonContext) -> None:
        del ctx
        volume_down(step=action.step)


@register
class SystemVolumeMuteHandler:
    action_type: ClassVar[str] = "system.volume.mute"

    def execute(self, action: SystemVolumeMuteAction, ctx: DaemonContext) -> None:
        del action, ctx
        volume_mute()


@register
class MediaPlayHandler:
    action_type: ClassVar[str] = "media.play"

    def execute(self, action: MediaPlayAction, ctx: DaemonContext) -> None:
        del action, ctx
        media_play()


@register
class MediaPauseHandler:
    action_type: ClassVar[str] = "media.pause"

    def execute(self, action: MediaPauseAction, ctx: DaemonContext) -> None:
        del action, ctx
        media_pause()


@register
class MediaNextHandler:
    action_type: ClassVar[str] = "media.next"

    def execute(self, action: MediaNextAction, ctx: DaemonContext) -> None:
        del action, ctx
        media_next()


@register
class MediaPrevHandler:
    action_type: ClassVar[str] = "media.prev"

    def execute(self, action: MediaPrevAction, ctx: DaemonContext) -> None:
        del action, ctx
        media_prev()
