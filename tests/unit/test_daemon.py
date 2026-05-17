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
    # key.chord which on Linux routes through sdac.platform._linux.subprocess.run
    # (patching canonical subprocess.run intercepts it). On Windows it routes
    # through keybd_event so the same mock doesn't apply — skip the second-press
    # check there.
    import sys
    if not sys.platform.startswith("win"):
        with patch("subprocess.run") as run:
            device.inject_press(1)
        assert run.call_count == 1


def test_daemon_hot_reload_picks_up_new_config(tmp_path: Path):
    cfg_path = tmp_path / "live.yaml"
    cfg_path.write_text(
        "version: 1\n"
        "default_profile: a\n"
        "profiles:\n"
        "  a:\n"
        "    default_page: home\n"
        "    pages:\n"
        "      home:\n"
        "        keys:\n"
        "          0:\n"
        "            icon: {text: A}\n"
        "            action: {type: shell, cmd: \"true\"}\n"
    )
    device = MockDevice()
    d = Daemon(device=device, config_path=cfg_path)
    d.load()
    d.render_current_page()
    d.start_watching()

    cfg_path.write_text(
        "version: 1\n"
        "default_profile: b\n"
        "profiles:\n"
        "  b:\n"
        "    default_page: home\n"
        "    pages:\n"
        "      home:\n"
        "        keys:\n"
        "          0:\n"
        "            icon: {text: B}\n"
        "            action: {type: shell, cmd: \"true\"}\n"
    )

    import time
    for _ in range(50):  # up to 5 seconds
        time.sleep(0.1)
        if d.current_profile == "b":
            break
    d.stop_watching()
    assert d.current_profile == "b"


def test_daemon_hot_reload_rejects_invalid_config_and_keeps_old(tmp_path: Path):
    cfg_path = tmp_path / "live.yaml"
    cfg_path.write_text(
        "version: 1\n"
        "default_profile: a\n"
        "profiles:\n"
        "  a:\n"
        "    default_page: home\n"
        "    pages:\n"
        "      home:\n"
        "        keys: {}\n"
    )
    device = MockDevice()
    d = Daemon(device=device, config_path=cfg_path)
    d.load()
    d.render_current_page()
    d.start_watching()

    cfg_path.write_text("version: 99\n")  # invalid

    import time
    time.sleep(0.8)
    d.stop_watching()

    assert d.current_profile == "a"


def test_daemon_start_obs_clients_skips_unreachable(monkeypatch: pytest.MonkeyPatch):
    """A host that won't connect just gets logged; daemon continues."""
    from unittest.mock import MagicMock, patch

    from sdac.obs.client import OBSConnectError

    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "abc")
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "env_var.yaml")
    d.load()

    with patch("sdac.daemon.OBSClient") as oc:
        instance = MagicMock()
        instance.start.side_effect = OBSConnectError("nope")
        oc.return_value = instance
        d.start_obs_clients()
    assert d._obs_clients == []


def test_daemon_start_obs_clients_keeps_successful_ones(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import MagicMock, patch
    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "abc")
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "env_var.yaml")
    d.load()
    with patch("sdac.daemon.OBSClient") as oc:
        instance = MagicMock()
        instance.start.return_value = None
        oc.return_value = instance
        d.start_obs_clients()
    assert len(d._obs_clients) == 1
    d.stop_obs_clients()
    instance.stop.assert_called_once()
