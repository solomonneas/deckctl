"""Action handler protocol and DaemonContext protocol.

Handlers receive a typed action and a DaemonContext that exposes only the
methods they may call back into. This keeps actions and the daemon loosely
coupled.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable


@runtime_checkable
class DaemonContext(Protocol):
    """The subset of the daemon that action handlers are allowed to call."""

    def switch_page(self, name: str) -> None: ...

    def switch_profile(self, name: str) -> None: ...

    def obs_host_url(self, name: str) -> str: ...


@runtime_checkable
class ActionHandler(Protocol):
    """Each handler advertises its action_type and implements execute()."""

    action_type: ClassVar[str]

    def execute(self, action: Any, ctx: DaemonContext) -> None: ...
