from __future__ import annotations

import logging
import subprocess
from unittest.mock import patch

import deckctl.actions  # noqa: F401 - ensures handlers are registered
from deckctl.actions import get_handler
from deckctl.config import ShellAction


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
    assert kwargs.get("check") is False


def test_shell_action_logs_nonzero_exit_status(caplog):
    action = ShellAction(type="shell", cmd="exit 7")
    result = subprocess.CompletedProcess(args=action.cmd, returncode=7)
    with (
        caplog.at_level(logging.WARNING, logger="deckctl.actions.shell"),
        patch("subprocess.run", return_value=result),
    ):
        get_handler("shell").execute(action, _NullCtx())
    assert "shell action exited with status 7" in caplog.text


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
