"""Navigation actions: page.go and profile.switch.

These don't shell out — they call back into the daemon via DaemonContext.
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
