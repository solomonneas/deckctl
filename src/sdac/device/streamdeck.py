"""Real Stream Deck wrapper around the upstream `streamdeck` library.

The daemon never imports `streamdeck.*` directly - all HID code lives here.
"""

from __future__ import annotations

from typing import Any

from PIL import Image
from StreamDeck.DeviceManager import DeviceManager  # type: ignore[import-untyped]
from StreamDeck.ImageHelpers import PILHelper  # type: ignore[import-untyped]

from sdac.device.base import KeyCallback, KeyEvent
from sdac.errors import SdacError


class DeviceNotFoundError(SdacError):
    """Raised when no Stream Deck device is enumerated on the bus."""


class StreamDeckDevice:
    """Adapter from a `streamdeck.StreamDeck` instance to our `Device` protocol."""

    def __init__(self, deck: Any) -> None:
        # `deck` is a `StreamDeck.Devices.StreamDeck.StreamDeck` subclass; we
        # treat it as `Any` because that library does not ship type stubs.
        self._deck = deck
        self._callbacks: list[KeyCallback] = []
        self._open = False

    @classmethod
    def enumerate_first(cls) -> StreamDeckDevice:
        """Return the first Stream Deck found, or raise DeviceNotFoundError."""
        decks = DeviceManager().enumerate()
        if not decks:
            raise DeviceNotFoundError(
                "no Stream Deck device found (check USB connection + udev permissions)"
            )
        return cls(decks[0])

    @classmethod
    def enumerate_first_or_none(cls) -> StreamDeckDevice | None:
        """Like enumerate_first but returns None instead of raising."""
        decks = DeviceManager().enumerate()
        if not decks:
            return None
        return cls(decks[0])

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def key_count(self) -> int:
        return int(self._deck.key_count())

    def open(self) -> None:
        if not self._open:
            self._deck.open()
            self._deck.reset()
            self._deck.set_key_callback(self._on_press)
            self._open = True

    def close(self) -> None:
        if self._open:
            try:
                self._deck.reset()
            finally:
                self._deck.close()
            self._open = False

    def set_key_image(self, key: int, image: Image.Image) -> None:
        if not 0 <= key < self.key_count:
            raise IndexError(f"key {key} out of range 0..{self.key_count - 1}")
        # PILHelper encapsulates any rotation / format quirks per device variant.
        # We pass our 72x72 RGB image; PILHelper converts to the device's native
        # JPEG bytes.
        native = PILHelper.to_native_key_format(self._deck, image)
        self._deck.set_key_image(key, native)

    def register_key_callback(self, callback: KeyCallback) -> None:
        self._callbacks.append(callback)

    def _on_press(self, _deck: Any, key: int, state: bool) -> None:
        ev = KeyEvent(key=key, pressed=state)
        for cb in list(self._callbacks):
            cb(ev)
