"""Windows implementations of platform-dependent action primitives.

`send_chord`, `type_text`, and the four `media_*` functions are implemented
via pywin32's keybd_event. `volume_*` remains NotImplementedError - Phase 4b
will wire pycaw or shell to nircmd.

Untested on the Linux dev machine; correctness will be verified when the
Stream Deck is plugged into the Windows host and a daemon is running.
"""

from __future__ import annotations

import subprocess
import webbrowser

# Windows virtual key codes for media keys
# (https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes)
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PREV_TRACK = 0xB1
_VK_MEDIA_STOP = 0xB2
_VK_MEDIA_PLAY_PAUSE = 0xB3

# Modifier virtual key codes (subset used by send_chord)
_VK_MODIFIERS = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
    "meta": 0x5B,
    "super": 0x5B,
    "cmd": 0x5B,
}

# Named special keys. Lowercased; aliases collapse to the same VK.
# Reference: https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes
_VK_SPECIAL = {
    "return": 0x0D, "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08,
    "space": 0x20,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21, "pgup": 0x21,
    "pagedown": 0x22, "pgdn": 0x22,
    "insert": 0x2D, "ins": 0x2D,
    "delete": 0x2E, "del": 0x2E,
    "apostrophe": 0xDE,  # OEM_7 (matches xdotool's "apostrophe" token)
    **{f"f{i}": 0x6F + i for i in range(1, 13)},  # F1=0x70 .. F12=0x7B
}
_KEYEVENTF_KEYUP = 0x0002


def _keybd_event(vk: int, up: bool = False) -> None:
    """Send a single key down or up via pywin32's keybd_event."""
    import win32api  # type: ignore[import-untyped]
    flags = _KEYEVENTF_KEYUP if up else 0
    win32api.keybd_event(vk, 0, flags, 0)


def _vk_for(token: str) -> int:
    """Resolve a chord token to a virtual key code.

    Accepts: known modifiers (ctrl, shift, ...), named special keys (Return,
    Tab, Escape, arrows, F1-F12, etc.), or any single character. pywin32 is
    only imported on the single-char fallback path so the named-key paths
    work in environments without pywin32 (e.g. our Linux CI unit tests).
    """
    token = token.lower()
    if token in _VK_MODIFIERS:
        return _VK_MODIFIERS[token]
    if token in _VK_SPECIAL:
        return _VK_SPECIAL[token]
    if len(token) == 1:
        import win32api
        # VkKeyScan returns the VK code in the low byte and shift state in the high byte.
        vk: int = win32api.VkKeyScan(token) & 0xFF
        return vk
    raise ValueError(f"unrecognized chord token: {token!r}")


def send_chord(keys: str) -> None:
    """Send a chord like 'ctrl+shift+t'."""
    tokens = [t.strip() for t in keys.split("+") if t.strip()]
    vks = [_vk_for(t) for t in tokens]
    for vk in vks:
        _keybd_event(vk, up=False)
    for vk in reversed(vks):
        _keybd_event(vk, up=True)


def type_text(text: str) -> None:
    """Type a literal string via win32 one character at a time."""
    import win32api
    for ch in text:
        vk_and_shift = win32api.VkKeyScan(ch)
        vk = vk_and_shift & 0xFF
        shift = (vk_and_shift >> 8) & 0xFF
        if shift & 1:
            _keybd_event(_VK_MODIFIERS["shift"], up=False)
        _keybd_event(vk, up=False)
        _keybd_event(vk, up=True)
        if shift & 1:
            _keybd_event(_VK_MODIFIERS["shift"], up=True)


def _todo(name: str) -> None:
    raise NotImplementedError(
        f"platform function {name!r} not yet implemented on Windows "
        "(volume control needs pycaw; queued for Phase 4b)"
    )


def volume_up(step: int = 5) -> None:
    del step
    _todo("volume_up")


def volume_down(step: int = 5) -> None:
    del step
    _todo("volume_down")


def volume_mute() -> None:
    _todo("volume_mute")


def media_play() -> None:
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=False)
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=True)


def media_pause() -> None:
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=False)
    _keybd_event(_VK_MEDIA_PLAY_PAUSE, up=True)


def media_next() -> None:
    _keybd_event(_VK_MEDIA_NEXT_TRACK, up=False)
    _keybd_event(_VK_MEDIA_NEXT_TRACK, up=True)


def media_prev() -> None:
    _keybd_event(_VK_MEDIA_PREV_TRACK, up=False)
    _keybd_event(_VK_MEDIA_PREV_TRACK, up=True)


def open_url(url: str) -> None:
    webbrowser.open(url)


def open_app(path: str) -> None:
    """Launch a binary detached. On Windows we don't use start_new_session;
    `Popen` alone gives the child its own console + process group."""
    subprocess.Popen([path])
