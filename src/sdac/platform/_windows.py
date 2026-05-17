"""Windows stubs. Phase 4 fills these in with pywin32 / SendKeys equivalents."""

from __future__ import annotations


def _todo(name: str) -> None:
    raise NotImplementedError(f"platform function {name!r} not implemented on Windows (Phase 4)")


def send_chord(keys: str) -> None:
    _todo("send_chord")


def type_text(text: str) -> None:
    _todo("type_text")


def volume_up(step: int = 5) -> None:
    _todo("volume_up")


def volume_down(step: int = 5) -> None:
    _todo("volume_down")


def volume_mute() -> None:
    _todo("volume_mute")


def media_play() -> None:
    _todo("media_play")


def media_pause() -> None:
    _todo("media_pause")


def media_next() -> None:
    _todo("media_next")


def media_prev() -> None:
    _todo("media_prev")


def open_url(url: str) -> None:
    _todo("open_url")


def open_app(path: str) -> None:
    _todo("open_app")
