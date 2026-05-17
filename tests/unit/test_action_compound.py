from __future__ import annotations

from unittest.mock import patch

import pytest

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import CompoundAction, ShellAction


class _NullCtx:
    def switch_page(self, name: str) -> None: ...
    def switch_profile(self, name: str) -> None: ...


def test_compound_runs_actions_in_order():
    actions = [
        ShellAction(type="shell", cmd="echo 1"),
        ShellAction(type="shell", cmd="echo 2"),
    ]
    compound = CompoundAction(type="compound", actions=actions)
    with patch("subprocess.run") as run:
        get_handler("compound").execute(compound, _NullCtx())
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == "echo 1"
    assert run.call_args_list[1].args[0] == "echo 2"


def test_compound_stops_on_first_failure_by_default():
    import subprocess

    actions = [
        ShellAction(type="shell", cmd="fail"),
        ShellAction(type="shell", cmd="never"),
    ]
    compound = CompoundAction(type="compound", actions=actions)
    with (
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "fail")),
        pytest.raises(subprocess.CalledProcessError),
    ):
        get_handler("compound").execute(compound, _NullCtx())


def test_compound_continue_on_error_runs_all():
    import subprocess

    actions = [
        ShellAction(type="shell", cmd="fail"),
        ShellAction(type="shell", cmd="next"),
    ]
    compound = CompoundAction(type="compound", actions=actions, continue_on_error=True)
    calls: list = []

    def fake(cmd, **kwargs):
        del kwargs
        calls.append(cmd)
        if cmd == "fail":
            raise subprocess.CalledProcessError(1, cmd)

    with patch("subprocess.run", side_effect=fake):
        get_handler("compound").execute(compound, _NullCtx())
    assert calls == ["fail", "next"]
