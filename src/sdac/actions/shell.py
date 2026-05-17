"""Shell action: run a command via the shell."""

from __future__ import annotations

import subprocess
from typing import Any, ClassVar

from sdac.actions import register
from sdac.actions.base import DaemonContext
from sdac.config import ShellAction


@register
class ShellHandler:
    action_type: ClassVar[str] = "shell"

    def execute(self, action: ShellAction, ctx: DaemonContext) -> None:
        del ctx  # unused; included for protocol compliance
        kwargs: dict[str, Any] = {"shell": True, "check": True}
        if action.cwd:
            kwargs["cwd"] = action.cwd
        if action.shell:
            kwargs["executable"] = action.shell
        subprocess.run(action.cmd, **kwargs)
