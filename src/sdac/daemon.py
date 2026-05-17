"""Daemon orchestrator.

Owns the device and config. Handles key-press dispatch via the action registry.
The daemon is synchronous: key callbacks (from the device's HID thread or a
mock's direct call) run handlers in-line. Phase 3 will add background event
loops for OBS websocket subscriptions.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PIL import Image

from sdac.actions import get_handler
from sdac.config import Config, load_config
from sdac.device import Device, KeyEvent
from sdac.render import KEY_SIZE, render_key

log = logging.getLogger(__name__)


class Daemon:
    """Cross-platform Stream Deck driver.

    Phase 2a behavior: load config, render the default profile/page, dispatch
    presses, allow handlers to navigate via switch_page / switch_profile.
    Phase 2a does NOT yet watch the config file (Task 13) or recover from
    device unplug (Task 14).
    """

    def __init__(self, device: Device, config_path: str | Path) -> None:
        self._device = device
        self._config_path = Path(config_path)
        self._config: Config | None = None
        self._current_profile: str | None = None
        self._current_page: str | None = None
        self._lock = threading.RLock()
        self._device.register_key_callback(self._on_key)

    # ----- DaemonContext protocol -----

    def switch_page(self, name: str) -> None:
        with self._lock:
            assert self._config is not None and self._current_profile is not None
            profile = self._config.profiles[self._current_profile]
            if name not in profile.pages:
                log.error(
                    "switch_page: page %r not in profile %r", name, self._current_profile
                )
                return
            self._current_page = name
        self.render_current_page()

    def switch_profile(self, name: str) -> None:
        with self._lock:
            assert self._config is not None
            if name not in self._config.profiles:
                log.error("switch_profile: profile %r not found", name)
                return
            self._current_profile = name
            self._current_page = self._config.profiles[name].default_page
        self.render_current_page()

    # ----- Lifecycle -----

    def load(self) -> None:
        """Parse the config file and reset to its default profile/page."""
        cfg = load_config(self._config_path)
        with self._lock:
            self._config = cfg
            self._current_profile = cfg.default_profile
            self._current_page = cfg.profiles[cfg.default_profile].default_page

    @property
    def current_profile(self) -> str | None:
        return self._current_profile

    @property
    def current_page(self) -> str | None:
        return self._current_page

    # ----- Rendering -----

    def render_current_page(self) -> None:
        """Push an image for every key on the current page (blanks for empty slots)."""
        with self._lock:
            assert self._config is not None
            assert self._current_profile is not None
            assert self._current_page is not None
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            keys = dict(page.keys)
        if not self._device.is_open:
            self._device.open()
        blank = Image.new("RGB", (KEY_SIZE, KEY_SIZE), "#000000")
        for idx in range(self._device.key_count):
            img = render_key(keys[idx], state="idle") if idx in keys else blank
            try:
                self._device.set_key_image(idx, img)
            except Exception:
                log.exception("failed to set key %d image", idx)

    # ----- Key dispatch -----

    def _on_key(self, event: KeyEvent) -> None:
        if not event.pressed:
            return
        with self._lock:
            if (
                self._config is None
                or self._current_profile is None
                or self._current_page is None
            ):
                return
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            key_cfg = page.keys.get(event.key)
        if key_cfg is None:
            return
        try:
            handler = get_handler(key_cfg.action.type)
            handler.execute(key_cfg.action, self)
        except Exception:
            log.exception("action %r on key %d raised", key_cfg.action.type, event.key)
