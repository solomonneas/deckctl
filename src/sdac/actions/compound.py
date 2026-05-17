"""Compound action: run a sequence of sub-actions."""

from __future__ import annotations

import logging
from typing import ClassVar

from sdac.actions import get_handler, register
from sdac.actions.base import DaemonContext
from sdac.config import CompoundAction

log = logging.getLogger(__name__)


@register
class CompoundHandler:
    action_type: ClassVar[str] = "compound"

    def execute(self, action: CompoundAction, ctx: DaemonContext) -> None:
        for i, sub in enumerate(action.actions):
            handler = get_handler(sub.type)
            try:
                handler.execute(sub, ctx)
            except Exception:
                if action.continue_on_error:
                    log.exception("compound sub-action %d (%s) failed; continuing", i, sub.type)
                    continue
                raise
