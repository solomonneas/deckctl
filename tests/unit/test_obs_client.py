from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sdac.obs.client import OBSClient, OBSConnectError, OBSEvent


def test_obs_event_dataclass_holds_kind_qualifier_active():
    ev = OBSEvent(host="roc", kind="obs.recording.state", qualifier=None, active=True)
    assert ev.host == "roc"
    assert ev.kind == "obs.recording.state"
    assert ev.qualifier is None
    assert ev.active is True


def test_obs_client_constructor_does_not_connect():
    """Constructing OBSClient with a callback is cheap; .start() opens the socket."""
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    assert not c.is_connected


def test_obs_client_start_calls_event_client_constructor_with_parsed_url():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/secret", on_event=cb)
    with patch("obsws_python.EventClient") as ec:
        c.start()
    ec.assert_called_once()
    kwargs = ec.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 4455
    assert kwargs["password"] == "secret"
    assert c.is_connected


def test_obs_client_start_raises_obs_connect_error_on_failure():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    with (
        patch("obsws_python.EventClient", side_effect=OSError("connection refused")),
        pytest.raises(OBSConnectError, match="connection refused"),
    ):
        c.start()
    assert not c.is_connected


def test_obs_client_stop_disconnects():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/secret", on_event=cb)
    fake_event_client = MagicMock()
    with patch("obsws_python.EventClient", return_value=fake_event_client):
        c.start()
    c.stop()
    fake_event_client.disconnect.assert_called_once()
    assert not c.is_connected


def test_obs_client_translates_record_state_changed_event_to_callback():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.output_state = "OBS_WEBSOCKET_OUTPUT_STARTED"
    c._on_record_state_changed(data)
    cb.assert_called_once()
    ev = cb.call_args.args[0]
    assert isinstance(ev, OBSEvent)
    assert ev.host == "roc"
    assert ev.kind == "obs.recording.state"
    assert ev.active is True


def test_obs_client_translates_record_state_stopped_event_to_inactive():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.output_state = "OBS_WEBSOCKET_OUTPUT_STOPPED"
    c._on_record_state_changed(data)
    ev = cb.call_args.args[0]
    assert ev.active is False


def test_obs_client_translates_scene_change():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.scene_name = "Camera"
    c._on_current_program_scene_changed(data)
    ev = cb.call_args.args[0]
    assert ev.kind == "obs.scene.current"
    assert ev.qualifier == "Camera"
    assert ev.active is True


def test_obs_client_translates_input_mute_state():
    cb = MagicMock()
    c = OBSClient(host="roc", url="obsws://127.0.0.1:4455/x", on_event=cb)
    data = MagicMock()
    data.input_name = "Mic"
    data.input_muted = True
    c._on_input_mute_state_changed(data)
    ev = cb.call_args.args[0]
    assert ev.kind == "obs.input.muted"
    assert ev.qualifier == "Mic"
    assert ev.active is True
