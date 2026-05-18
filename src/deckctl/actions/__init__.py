"""Action handler registry.

Handler modules register themselves by decorating their class with
`@register`. Concrete handler modules are eager-imported from this file
in later tasks so their `@register` decorators fire at import time.
"""

from __future__ import annotations

from typing import TypeVar

from deckctl.actions.base import ActionHandler

HANDLERS: dict[str, ActionHandler] = {}

_H = TypeVar("_H", bound=type[ActionHandler])


def register(cls: _H) -> _H:
    """Class decorator that instantiates the handler and adds it to HANDLERS."""
    instance = cls()
    HANDLERS[instance.action_type] = instance
    return cls


def get_handler(action_type: str) -> ActionHandler:
    """Look up a registered handler by its action_type. Raises KeyError if unknown."""
    try:
        return HANDLERS[action_type]
    except KeyError as e:
        raise KeyError(f"no handler registered for action type {action_type!r}") from e


# Eager imports - every concrete handler module's `@register` runs at import.
# Order is irrelevant but keep alphabetical for tidiness.
from deckctl.actions import (  # noqa: E402, F401
    compound,
    keys,
    navigation,
    obs,
    opening,
    shell,
    system_audio,
)
