"""Device abstraction + concrete implementations."""

from deckctl.device.base import Device, KeyCallback, KeyEvent
from deckctl.device.mock import MockDevice
from deckctl.device.streamdeck import DeviceNotFoundError, StreamDeckDevice

__all__ = [
    "Device",
    "DeviceNotFoundError",
    "KeyCallback",
    "KeyEvent",
    "MockDevice",
    "StreamDeckDevice",
]
