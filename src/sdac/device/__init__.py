"""Device abstraction + concrete implementations."""

from sdac.device.base import Device, KeyCallback, KeyEvent
from sdac.device.mock import MockDevice
from sdac.device.streamdeck import DeviceNotFoundError, StreamDeckDevice

__all__ = [
    "Device",
    "DeviceNotFoundError",
    "KeyCallback",
    "KeyEvent",
    "MockDevice",
    "StreamDeckDevice",
]
