"""Daemon orchestrator.

Owns the device and config. Handles key-press dispatch via the action registry.
Key callbacks hand actions to background threads so a slow handler cannot
block later device events.
"""

from __future__ import annotations

import logging
import signal
import threading
from pathlib import Path

from PIL import Image
from watchdog.events import (
    DirMovedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from deckctl.actions import get_handler
from deckctl.config import Action, Config, Indicator, ProfileRule, load_config
from deckctl.device import Device, KeyEvent
from deckctl.obs.client import OBSClient, OBSConnectError, OBSEvent
from deckctl.render import KEY_SIZE, render_key
from deckctl.watchers import ActiveWindow, NullWatcher, Watcher

log = logging.getLogger(__name__)


class Daemon:
    """Cross-platform Stream Deck driver.

    Phase 2a behavior: load config, render the default profile/page, dispatch
    presses, allow handlers to navigate via switch_page / switch_profile.
    Phase 2a does NOT yet watch the config file (Task 13) or recover from
    device unplug (Task 14).
    """

    def __init__(
        self,
        device: Device,
        config_path: str | Path,
        *,
        watcher: Watcher | None = None,
    ) -> None:
        self._device = device
        self._config_path = Path(config_path)
        self._config: Config | None = None
        self._current_profile: str | None = None
        self._current_page: str | None = None
        self._lock = threading.RLock()
        self._observer: BaseObserver | None = None
        self._indicator_state: dict[tuple[str, str, str | None], bool] = {}
        self._obs_clients: list[OBSClient] = []
        self._device.register_key_callback(self._on_key)
        self._watcher: Watcher = watcher if watcher is not None else NullWatcher()

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

    def obs_host_url(self, name: str) -> str:
        with self._lock:
            assert self._config is not None
            if name not in self._config.obs_hosts:
                raise KeyError(f"unknown obs host: {name}")
            return self._config.obs_hosts[name].url

    def _indicator_active(self, ind: Indicator) -> bool:
        """Look up the current cached state for an indicator binding."""
        if ind.bind == "obs.scene.current":
            qualifier = ind.scene
        elif ind.bind == "obs.input.muted":
            qualifier = ind.input_name
        else:
            qualifier = None
        return self._indicator_state.get((ind.bind, ind.host, qualifier), False)

    def _update_indicator(
        self,
        bind_kind: str,
        host: str,
        qualifier: str | None,
        active: bool,
    ) -> list[int]:
        """Update the state map and return the keys on the current page that need re-rendering."""
        with self._lock:
            if bind_kind == "obs.scene.current":
                # Scene change: zero out all other scenes on this host so the
                # previously-active key flips off.
                for k_state in list(self._indicator_state):
                    bk, h, _q = k_state
                    if bk == "obs.scene.current" and h == host:
                        self._indicator_state[k_state] = False
                self._indicator_state[(bind_kind, host, qualifier)] = active
            else:
                key = (bind_kind, host, qualifier)
                prev = self._indicator_state.get(key)
                self._indicator_state[key] = active
                if prev == active:
                    return []
            if (
                self._config is None
                or self._current_profile is None
                or self._current_page is None
            ):
                return []
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            affected: list[int] = []
            for idx, k in page.keys.items():
                if k.indicator is None:
                    continue
                ind = k.indicator
                if ind.bind != bind_kind or ind.host != host:
                    continue
                if ind.bind == "obs.input.muted" and ind.input_name != qualifier:
                    continue
                affected.append(idx)
            return affected

    def _rerender_keys(self, indices: list[int]) -> None:
        """Re-render specific keys without touching the rest of the page."""
        with self._lock:
            assert self._config is not None
            assert self._current_profile is not None
            assert self._current_page is not None
            page = self._config.profiles[self._current_profile].pages[self._current_page]
            keys = {i: page.keys.get(i) for i in indices}
        if not self._device.is_open:
            return
        for idx, k in keys.items():
            if k is None:
                continue
            active = bool(k.indicator and self._indicator_active(k.indicator))
            try:
                img = render_key(k, state="active" if active else "idle")
                self._device.set_key_image(idx, img)
            except Exception:
                log.exception("indicator re-render failed on key %d", idx)

    def on_obs_event(self, event: OBSEvent) -> None:
        """Callback invoked by OBSClient when an event arrives on its worker thread."""
        affected = self._update_indicator(event.kind, event.host, event.qualifier, event.active)
        if affected:
            self._rerender_keys(affected)

    def start_obs_clients(self) -> None:
        """Open a websocket connection to each configured obs_host. Best-effort."""
        with self._lock:
            assert self._config is not None
            hosts = list(self._config.obs_hosts.items())
        for name, host in hosts:
            client = OBSClient(host=name, url=host.url, on_event=self.on_obs_event)
            try:
                client.start()
            except OBSConnectError as e:
                log.warning("OBS host %s unreachable: %s", name, e)
                continue
            self._obs_clients.append(client)
            log.info("OBS host %s subscribed for events", name)

    def stop_obs_clients(self) -> None:
        for c in self._obs_clients:
            c.stop()
        self._obs_clients.clear()

    # ----- Active-window auto-switch -----

    def start_watching_windows(self) -> None:
        """Subscribe to the active-window watcher; switch profile on match."""
        self._watcher.start(self._on_active_window)

    def stop_watching_windows(self) -> None:
        self._watcher.stop()

    def _on_active_window(self, window: ActiveWindow) -> None:
        with self._lock:
            if self._config is None:
                return
            rules = list(self._config.profile_rules)
        for rule in rules:
            if self._rule_matches(rule, window):
                if rule.profile != self._current_profile:
                    self.switch_profile(rule.profile)
                return

    def _rule_matches(self, rule: ProfileRule, window: ActiveWindow) -> bool:
        if window.app_class and window.app_class in rule.when.app_class:
            return True
        return bool(window.app_name and window.app_name in rule.when.app_name)

    # ----- Lifecycle -----

    def load(self) -> None:
        """Parse the config file and reset to its default profile/page."""
        cfg = load_config(self._config_path)
        with self._lock:
            self._config = cfg
            self._current_profile = cfg.default_profile
            self._current_page = cfg.profiles[cfg.default_profile].default_page

    def start_watching(self) -> None:
        """Begin watching the config file for changes; reload on every modify."""
        if self._observer is not None:
            return

        daemon = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event: FileSystemEvent) -> None:
                if Path(str(event.src_path)).resolve() == daemon._config_path.resolve():
                    daemon._reload()

            def on_created(self, event: FileSystemEvent) -> None:
                if Path(str(event.src_path)).resolve() == daemon._config_path.resolve():
                    daemon._reload()

            def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
                if Path(str(event.dest_path)).resolve() == daemon._config_path.resolve():
                    daemon._reload()

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self._config_path.parent), recursive=False)
        self._observer.start()

    def stop_watching(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=2.0)
        self._observer = None

    def _reload(self) -> None:
        try:
            new_cfg = load_config(self._config_path)
        except Exception:
            log.exception("config reload rejected; keeping previous config")
            return
        with self._lock:
            cur_profile = self._current_profile
            cur_page = self._current_page
            if cur_profile in new_cfg.profiles:
                profile = new_cfg.profiles[cur_profile]
                if cur_page not in profile.pages:
                    cur_page = profile.default_page
            else:
                cur_profile = new_cfg.default_profile
                cur_page = new_cfg.profiles[new_cfg.default_profile].default_page
            self._config = new_cfg
            self._current_profile = cur_profile
            self._current_page = cur_page
        self.render_current_page()
        log.info("config reloaded; active=%s/%s", self._current_profile, self._current_page)

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
            if idx in keys:
                k = keys[idx]
                active = bool(k.indicator and self._indicator_active(k.indicator))
                img = render_key(k, state="active" if active else "idle")
            else:
                img = blank
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
        threading.Thread(
            target=self._execute_action,
            args=(key_cfg.action, event.key),
            name=f"deckctl-action-{event.key}",
            daemon=True,
        ).start()

    def _execute_action(self, action: Action, key: int) -> None:
        try:
            handler = get_handler(action.type)
            handler.execute(action, self)
        except Exception:
            log.exception("action %r on key %d raised", action.type, key)

    def run_forever(self) -> None:
        """Block until SIGINT / SIGTERM. Used by the `deckctl daemon` CLI verb."""
        stop = threading.Event()

        def handle(signum: int, frame: object) -> None:
            del frame
            log.info("received signal %d; stopping", signum)
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, handle)

        self.start_obs_clients()
        self.start_watching_windows()
        try:
            while not stop.is_set():
                stop.wait(timeout=1.0)
        finally:
            self.stop_obs_clients()
            self.stop_watching_windows()
            self.stop_watching()
            if self._device.is_open:
                self._device.close()
