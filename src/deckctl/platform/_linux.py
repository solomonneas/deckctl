"""Linux implementations of platform-dependent action primitives.

Every function shells out and raises CalledProcessError on failure so the
action dispatcher can surface that to the user. We do NOT swallow errors here.
"""

from __future__ import annotations

import subprocess
import webbrowser


def send_chord(keys: str) -> None:
    """Send a keystroke chord (e.g. 'ctrl+shift+t')."""
    subprocess.run(["xdotool", "key", keys], check=True)


def type_text(text: str) -> None:
    """Type a literal string. --clearmodifiers prevents a held key from corrupting input."""
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text], check=True)


def volume_up(step: int = 5) -> None:
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step}%"], check=True)


def volume_down(step: int = 5) -> None:
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step}%"], check=True)


def volume_mute() -> None:
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True)


def media_play() -> None:
    subprocess.run(["playerctl", "play"], check=True)


def media_pause() -> None:
    subprocess.run(["playerctl", "pause"], check=True)


def media_next() -> None:
    subprocess.run(["playerctl", "next"], check=True)


def media_prev() -> None:
    subprocess.run(["playerctl", "previous"], check=True)


def open_url(url: str) -> None:
    webbrowser.open(url)


def open_app(path: str) -> None:
    """Launch a binary detached so the daemon doesn't reap its lifecycle."""
    subprocess.Popen([path], start_new_session=True)
