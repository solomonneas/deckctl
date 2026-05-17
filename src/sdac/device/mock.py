"""In-memory device used by the daemon test suite. No HID, no threads."""

from __future__ import annotations

from PIL import Image

from sdac.device.base import KeyCallback, KeyEvent


class MockDevice:
    """A `Device` implementation that records pushed images and lets tests
    inject button presses."""

    def __init__(self, key_count: int = 15) -> None:
        self._key_count = key_count
        self._open = False
        self._callbacks: list[KeyCallback] = []
        self.images_pushed: dict[int, Image.Image] = {}

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def key_count(self) -> int:
        return self._key_count

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def set_key_image(self, key: int, image: Image.Image) -> None:
        if not 0 <= key < self._key_count:
            raise IndexError(f"key {key} out of range 0..{self._key_count - 1}")
        self.images_pushed[key] = image.copy()

    def register_key_callback(self, callback: KeyCallback) -> None:
        self._callbacks.append(callback)

    def inject_press(self, key: int) -> None:
        """Fire press + release for `key`. Tests use this to simulate a button push."""
        for cb in list(self._callbacks):
            cb(KeyEvent(key=key, pressed=True))
        for cb in list(self._callbacks):
            cb(KeyEvent(key=key, pressed=False))
