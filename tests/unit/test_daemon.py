from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

import sdac.actions  # noqa: F401 — registers handlers
from sdac.daemon import Daemon
from sdac.device import MockDevice
from sdac.errors import ConfigError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_daemon_loads_config_and_renders_default_profile_home_page():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    # comprehensive.yaml's default profile is `coding` with `home` page; the
    # home page configures 8 keys (indices 0..7). The mock should have all
    # 15 keys pushed (configured ones rendered, empty slots as blanks).
    assert device.is_open
    assert set(device.images_pushed.keys()) == set(range(15))


def test_daemon_dispatches_key_press_to_handler():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    with patch("subprocess.run") as run:
        device.inject_press(0)  # key 0 on coding/home is a shell action
    # Press fires once; release should not dispatch again.
    assert run.call_count == 1


def test_daemon_page_go_navigates_within_profile():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    device.images_pushed.clear()
    # key 5 on coding/home has action page.go(page=git)
    device.inject_press(5)
    assert d.current_page == "git"
    # render after page change pushed all 15 keys again
    assert set(device.images_pushed.keys()) == set(range(15))


def test_daemon_profile_switch_changes_profile_and_resets_to_default_page():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    # key 6 on coding/home has action profile.switch(profile=streaming)
    device.inject_press(6)
    assert d.current_profile == "streaming"
    assert d.current_page == "home"  # streaming.default_page


def test_daemon_load_propagates_config_error_on_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 99\n")
    device = MockDevice()
    d = Daemon(device=device, config_path=bad)
    with pytest.raises(ConfigError):
        d.load()


def test_daemon_handler_exception_does_not_crash_daemon(caplog):
    """An action that raises must be logged but the daemon stays up."""
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()

    def boom(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    with (
        caplog.at_level(logging.ERROR, logger="sdac.daemon"),
        patch("subprocess.run", side_effect=boom),
    ):
        device.inject_press(0)
    assert any(
        "boom" in rec.message or "boom" in str(rec.exc_info) for rec in caplog.records
    )
    # Daemon still wired up — a follow-on press still dispatches. Key 1 is
    # key.chord which routes through sdac.platform._linux.subprocess.run, and
    # patching the canonical subprocess.run name intercepts it.
    with patch("subprocess.run") as run:
        device.inject_press(1)
    assert run.call_count == 1
