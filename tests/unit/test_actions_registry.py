from __future__ import annotations

from typing import ClassVar

import pytest

from deckctl.actions import HANDLERS, get_handler, register
from deckctl.actions.base import ActionHandler, DaemonContext
from deckctl.config import ShellAction


class _FakeCtx:
    """A DaemonContext implementation for tests."""

    def __init__(self) -> None:
        self.page_switches: list[str] = []
        self.profile_switches: list[str] = []

    def switch_page(self, name: str) -> None:
        self.page_switches.append(name)

    def switch_profile(self, name: str) -> None:
        self.profile_switches.append(name)

    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")


def test_register_decorator_adds_to_handlers():
    initial = set(HANDLERS)

    @register
    class _Dummy:
        action_type = "_dummy"

        def execute(self, action, ctx):
            pass

    try:
        assert "_dummy" in HANDLERS
        assert isinstance(HANDLERS["_dummy"], _Dummy)
    finally:
        HANDLERS.pop("_dummy", None)
    assert set(HANDLERS) == initial


def test_get_handler_returns_registered_instance():
    @register
    class _Echo:
        action_type = "_echo"
        executed: ClassVar[list] = []

        def execute(self, action, ctx):
            self.executed.append(action)

    try:
        h = get_handler("_echo")
        action = ShellAction(type="shell", cmd="echo hi")
        h.execute(action, _FakeCtx())
        assert h.executed == [action]
    finally:
        HANDLERS.pop("_echo", None)


def test_get_handler_unknown_type_raises_key_error():
    with pytest.raises(KeyError, match="no handler"):
        get_handler("does.not.exist")


def test_daemon_context_protocol_is_runtime_checkable():
    ctx = _FakeCtx()
    assert isinstance(ctx, DaemonContext)


def test_action_handler_protocol_is_runtime_checkable():
    @register
    class _Y:
        action_type = "_y"

        def execute(self, action, ctx):
            pass

    try:
        assert isinstance(HANDLERS["_y"], ActionHandler)
    finally:
        HANDLERS.pop("_y", None)
