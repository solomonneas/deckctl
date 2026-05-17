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

    def execute(self, action: OpenUrlAction, ctx: DaemonContext) -> None:
        del ctx
        open_url(action.url)


@register
class OpenAppHandler:
    action_type: ClassVar[str] = "open.app"

    def execute(self, action: OpenAppAction, ctx: DaemonContext) -> None:
        del ctx
        if action.path:
            open_app(action.path)
            return
        # Pydantic guarantees exactly one of path/name is set.
        assert action.name is not None
        subprocess.Popen(["xdg-open", action.name], start_new_session=True)
