from __future__ import annotations

from unittest.mock import patch

import sdac.actions  # noqa: F401 — ensures handlers are registered
from sdac.actions import get_handler
from sdac.config import ShellAction


class _NullCtx:
    def switch_page(self, name: str) -> None:
        pass

    def switch_profile(self, name: str) -> None:
        pass

    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")


def test_shell_action_invokes_subprocess_run_with_shell_true():
    action = ShellAction(type="shell", cmd="echo hi")
    with patch("subprocess.run") as run:
        get_handler("shell").execute(action, _NullCtx())
    run.assert_called_once()
    args, kwargs = run.call_args
    assert args[0] == "echo hi"
    assert kwargs.get("shell") is True
    assert kwargs.get("check") is True


def test_shell_action_with_cwd_passes_cwd_to_subprocess():
    action = ShellAction(type="shell", cmd="ls", cwd="/tmp")
    with patch("subprocess.run") as run:
        get_handler("shell").execute(action, _NullCtx())
    _, kwargs = run.call_args
    assert kwargs.get("cwd") == "/tmp"


def test_shell_action_with_custom_shell():
    action = ShellAction(type="shell", cmd="echo hi", shell="/bin/zsh")
    with patch("subprocess.run") as run:
        get_handler("shell").execute(action, _NullCtx())
    _, kwargs = run.call_args
    assert kwargs.get("executable") == "/bin/zsh"
