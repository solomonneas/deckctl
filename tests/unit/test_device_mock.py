from __future__ import annotations

from PIL import Image

from sdac.device import MockDevice
from sdac.device.base import KeyEvent


def test_mock_device_open_close():
    d = MockDevice()
    assert not d.is_open
    d.open()
    assert d.is_open
    d.close()
    assert not d.is_open


def test_mock_device_key_count_defaults_to_15():
    assert MockDevice().key_count == 15


def test_mock_device_records_pushed_images():
    d = MockDevice()
    d.open()
    img = Image.new("RGB", (72, 72), "#ff0000")
    d.set_key_image(0, img)
    assert d.images_pushed[0].getpixel((0, 0)) == (255, 0, 0)


def test_mock_device_callback_fires_on_inject_press():
    d = MockDevice()
    d.open()
    events: list[KeyEvent] = []
    d.register_key_callback(lambda e: events.append(e))
    d.inject_press(3)
    assert events == [KeyEvent(key=3, pressed=True), KeyEvent(key=3, pressed=False)]


def test_mock_device_set_key_image_rejects_out_of_range():
    d = MockDevice()
    d.open()
    img = Image.new("RGB", (72, 72))
    try:
        d.set_key_image(99, img)
    except IndexError:
        return
    raise AssertionError("expected IndexError for key 99")
