"""Verify the Linux platform shim shells out to the right binaries with the
right args. We don't actually invoke xdotool/pactl/playerctl - we mock
subprocess.run and assert on the call shape.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

WINDOWS = sys.platform.startswith("win")
if WINDOWS:
    pytest.skip("Linux platform shim", allow_module_level=True)

from deckctl.platform._linux import (  # noqa: E402
    media_next,
    media_pause,
    media_play,
    media_prev,
    open_app,
    open_url,
    send_chord,
    type_text,
    volume_down,
    volume_mute,
    volume_up,
)


def test_send_chord_shells_to_xdotool():
    with patch("subprocess.run") as run:
        send_chord("ctrl+shift+t")
    run.assert_called_once_with(["xdotool", "key", "ctrl+shift+t"], check=True)


def test_type_text_shells_to_xdotool_with_clearmodifiers():
    with patch("subprocess.run") as run:
        type_text("console.log()")
    run.assert_called_once_with(
        ["xdotool", "type", "--clearmodifiers", "--", "console.log()"], check=True
    )


def test_volume_up_pactl_with_step():
    with patch("subprocess.run") as run:
        volume_up(step=5)
    run.assert_called_once_with(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], check=True
    )


def test_volume_down_pactl_with_step():
    with patch("subprocess.run") as run:
        volume_down(step=10)
    run.assert_called_once_with(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], check=True
    )


def test_volume_mute_toggles():
    with patch("subprocess.run") as run:
        volume_mute()
    run.assert_called_once_with(
        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True
    )


def test_media_play_uses_playerctl():
    with patch("subprocess.run") as run:
        media_play()
    run.assert_called_once_with(["playerctl", "play"], check=True)


def test_media_pause_uses_playerctl():
    with patch("subprocess.run") as run:
        media_pause()
    run.assert_called_once_with(["playerctl", "pause"], check=True)


def test_media_next_uses_playerctl():
    with patch("subprocess.run") as run:
        media_next()
    run.assert_called_once_with(["playerctl", "next"], check=True)


def test_media_prev_uses_playerctl():
    with patch("subprocess.run") as run:
        media_prev()
    run.assert_called_once_with(["playerctl", "previous"], check=True)


def test_open_url_uses_webbrowser():
    with patch("webbrowser.open") as wb:
        open_url("https://example.com")
    wb.assert_called_once_with("https://example.com")


def test_open_app_starts_detached():
    with patch("subprocess.Popen") as popen:
        open_app("/usr/bin/code")
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0] == ["/usr/bin/code"]
    assert kwargs.get("start_new_session") is True
