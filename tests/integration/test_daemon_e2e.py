"""End-to-end daemon test — exercises every handler category against MockDevice
in one run, with hot reload thrown in for good measure.

This test asserts Linux-specific platform call shapes (xdotool/pactl). Skipped
on Windows; Phase 4b will add a parallel Windows-shape integration test.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

if sys.platform.startswith("win"):
    pytest.skip("Linux-shape integration test", allow_module_level=True)

from deckctl.daemon import Daemon
from deckctl.device import MockDevice

FIXTURE = Path(__file__).parent.parent / "fixtures" / "configs" / "daemon_smoke.yaml"


def test_full_lifecycle_against_mock_device(tmp_path: Path):
    # Copy fixture to a writable location so we can edit it during the run.
    cfg = tmp_path / "smoke.yaml"
    cfg.write_text(FIXTURE.read_text())

    device = MockDevice()
    d = Daemon(device=device, config_path=cfg)
    d.load()
    d.render_current_page()
    d.start_watching()
    try:
        # Initial render covers all 15 keys.
        assert set(device.images_pushed.keys()) == set(range(15))

        # Shell action (key 0): subprocess.run is called with "true"
        with patch("subprocess.run") as run:
            device.inject_press(0)
        assert run.call_count == 1
        assert run.call_args.args[0] == "true"

        # Chord action (key 1) — goes through platform.send_chord -> subprocess.run
        with patch("deckctl.platform._linux.subprocess.run") as run:
            device.inject_press(1)
        run.assert_called_with(["xdotool", "key", "ctrl+t"], check=True)

        # Volume up (key 2)
        with patch("deckctl.platform._linux.subprocess.run") as run:
            device.inject_press(2)
        run.assert_called_with(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+2%"], check=True
        )

        # Compound (key 3 — two shell sub-actions)
        with patch("subprocess.run") as run:
            device.inject_press(3)
        assert run.call_count == 2

        # Page navigation (key 4)
        device.inject_press(4)
        assert d.current_page == "other"

        # Back-nav from the other page (key 0 on "other" goes back to home)
        device.images_pushed.clear()
        device.inject_press(0)
        assert d.current_page == "home"

        # Hot reload: rewrite config so default_profile changes
        cfg.write_text(
            "version: 1\ndefault_profile: changed\n"
            "profiles:\n"
            "  changed:\n    default_page: only\n"
            "    pages:\n      only:\n        keys: {}\n"
        )
        for _ in range(50):  # up to 5s for watchdog
            time.sleep(0.1)
            if d.current_profile == "changed":
                break
        assert d.current_profile == "changed"
        assert d.current_page == "only"
    finally:
        d.stop_watching()
        device.close()
