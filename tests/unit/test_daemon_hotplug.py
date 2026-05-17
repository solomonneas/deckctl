from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from sdac.daemon import Daemon
from sdac.device import MockDevice

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_render_after_reopen_resumes_cleanly():
    """Simulate device.close() then re-open via render_current_page()."""
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    assert device.is_open

    device.close()
    device.images_pushed.clear()

    d.render_current_page()
    assert device.is_open
    assert set(device.images_pushed.keys()) == set(range(15))


def test_set_key_image_failure_is_logged_and_skipped(caplog):
    """If set_key_image raises mid-render, daemon logs and continues with other keys."""

    class FlakyDevice(MockDevice):
        def __init__(self) -> None:
            super().__init__()
            self.fail_on_key: int | None = None

        def set_key_image(self, key: int, image: Image.Image) -> None:
            if key == self.fail_on_key:
                raise RuntimeError(f"simulated USB hiccup on key {key}")
            super().set_key_image(key, image)

    device = FlakyDevice()
    device.fail_on_key = 3
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    with caplog.at_level(logging.ERROR, logger="sdac.daemon"):
        d.render_current_page()
    assert 3 not in device.images_pushed
    # Other keys still rendered
    assert 0 in device.images_pushed
    assert any("key 3" in r.message or "key 3" in str(r) for r in caplog.records)
