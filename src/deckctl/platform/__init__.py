"""Platform-dependent primitives. Selects the right backend at import time."""

from __future__ import annotations

import sys

if sys.platform.startswith("win"):
    from deckctl.platform._windows import (
        media_next,
        media_pause,
        media_play,
        media_prev,
        open_app,
        open_url,
        send_chord,
        type_text,
        volume_down,
        volume_mute,
        volume_up,
    )
else:
    from deckctl.platform._linux import (
        media_next,
        media_pause,
        media_play,
        media_prev,
        open_app,
        open_url,
        send_chord,
        type_text,
        volume_down,
        volume_mute,
        volume_up,
    )

__all__ = [
    "media_next",
    "media_pause",
    "media_play",
    "media_prev",
    "open_app",
    "open_url",
    "send_chord",
    "type_text",
    "volume_down",
    "volume_mute",
    "volume_up",
]
