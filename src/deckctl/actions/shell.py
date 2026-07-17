"""Shell action: run a command via the shell."""

from __future__ import annotations

import logging
import subprocess
from typing import Any, ClassVar

from deckctl.actions import register
from deckctl.actions.base import DaemonContext
from deckctl.config import ShellAction

log = logging.getLogger(__name__)


@register
class ShellHandler:
    action_type: ClassVar[str] = "shell"

    def execute(self, action: ShellAction, ctx: DaemonContext) -> None:
        del ctx  # unused; included for protocol compliance
        kwargs: dict[str, Any] = {"shell": True, "check": False}
        if action.cwd:
            kwargs["cwd"] = action.cwd
        if action.shell:
            kwargs["executable"] = action.shell
        result = subprocess.run(action.cmd, **kwargs)
        if result.returncode != 0:
            log.warning("shell action exited with status %d", result.returncode)
