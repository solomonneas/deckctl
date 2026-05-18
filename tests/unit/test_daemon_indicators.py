from __future__ import annotations

from pathlib import Path

import pytest

import deckctl.actions  # noqa: F401
from deckctl.daemon import Daemon
from deckctl.device import MockDevice
from deckctl.obs.client import OBSEvent

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_indicator_active_initially_false():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    # streaming/home/key 1 has indicator bind=obs.recording.state host=roc
    rec_key = d._config.profiles["streaming"].pages["home"].keys[1]
    assert d._indicator_active(rec_key.indicator) is False


def test_on_obs_event_updates_state_map():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.render_current_page()
    d.switch_profile("streaming")
    device.images_pushed.clear()
    d.on_obs_event(OBSEvent(
        host="roc", kind="obs.recording.state", qualifier=None, active=True,
    ))
    rec_key = d._config.profiles["streaming"].pages["home"].keys[1]
    assert d._indicator_active(rec_key.indicator) is True
    # Key 1 should have been re-rendered (no full page repush)
    assert set(device.images_pushed.keys()) == {1}


def test_obs_event_for_other_host_does_not_trigger_render():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.switch_profile("streaming")
    device.images_pushed.clear()
    d.on_obs_event(OBSEvent(
        host="windows-host", kind="obs.recording.state", qualifier=None, active=True,
    ))
    assert device.images_pushed == {}


def test_obs_scene_change_flips_previously_active():
    """When the active scene changes, the previous scene's binding goes inactive."""
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.switch_profile("streaming")
    d.on_obs_event(OBSEvent(host="roc", kind="obs.scene.current", qualifier="Camera", active=True))
    assert d._indicator_state.get(("obs.scene.current", "roc", "Camera")) is True
    d.on_obs_event(OBSEvent(host="roc", kind="obs.scene.current", qualifier="Lobby", active=True))
    assert d._indicator_state[("obs.scene.current", "roc", "Camera")] is False
    assert d._indicator_state[("obs.scene.current", "roc", "Lobby")] is True


def test_obs_event_with_no_change_is_noop():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    d.switch_profile("streaming")
    d.on_obs_event(OBSEvent(host="roc", kind="obs.recording.state", qualifier=None, active=True))
    device.images_pushed.clear()
    d.on_obs_event(OBSEvent(host="roc", kind="obs.recording.state", qualifier=None, active=True))
    assert device.images_pushed == {}


def test_obs_host_url_lookup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DECKCTL_TEST_OBS_PASS", "letmein")
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "env_var.yaml")
    d.load()
    url = d.obs_host_url("roc")
    assert url == "obsws://127.0.0.1:4455/letmein"


def test_obs_host_url_unknown_raises():
    device = MockDevice()
    d = Daemon(device=device, config_path=FIXTURES / "comprehensive.yaml")
    d.load()
    with pytest.raises(KeyError, match="unknown obs host"):
        d.obs_host_url("ghost")
