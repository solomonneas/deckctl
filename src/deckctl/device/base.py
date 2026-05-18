"""Device abstraction. The daemon talks to this protocol; concrete devices
(StreamDeckDevice, MockDevice) implement it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PIL import Image


@dataclass(frozen=True)
class KeyEvent:
    """Press or release of a physical key."""

    key: int
    pressed: bool


KeyCallback = Callable[[KeyEvent], None]


@runtime_checkable
class Device(Protocol):
    """The minimum surface the daemon needs from a Stream Deck-like device."""

    @property
    def is_open(self) -> bool: ...

    @property
    def key_count(self) -> int: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def set_key_image(self, key: int, image: Image.Image) -> None: ...

    def register_key_callback(self, callback: KeyCallback) -> None: ...
