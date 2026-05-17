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

    def execute(self, action: KeyChordAction, ctx: DaemonContext) -> None:
        del ctx
        send_chord(action.keys)


@register
class KeyTextHandler:
    action_type: ClassVar[str] = "key.text"

    def execute(self, action: KeyTextAction, ctx: DaemonContext) -> None:
        del ctx
        type_text(action.text)
