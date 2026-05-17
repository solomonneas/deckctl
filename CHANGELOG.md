# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-17

Initial public release. Covers Phase 1 through Phase 4 of the implementation roadmap
(see `docs/superpowers/specs/2026-05-17-streamdeck-as-code-design.md`).

### Added

**Phase 1 — Foundation**
- Pydantic v2 schema for the YAML config (discriminated union over 21 action types).
- `${ENV_VAR}` substitution across the entire parsed YAML tree.
- POSIX file permission check (`--strict-perms`).
- `sdac validate <config>` CLI verb.
- Pillow + Pilmoji icon renderer (text, emoji, image-background, state variants).
- `sdac preview <config>` CLI verb — renders the full profile as a mosaic PNG.
- Bundled rsms/inter v4.0 Inter-Bold.ttf for deterministic icon rendering.
- GitHub Actions CI on Ubuntu + Windows, Python 3.11 + 3.12.

**Phase 2a — Daemon + actions**
- USB HID I/O via `python-elgato-streamdeck` for Stream Deck MK.2.
- Cross-platform `Device` protocol with `MockDevice` for tests.
- Synchronous threaded daemon, hot-reload via `watchdog`.
- Built-in action handlers: `shell`, `key.chord`, `key.text`, `open.url`, `open.app`, `system.volume.up/down/mute`, `media.play/pause/next/prev`, `page.go`, `profile.switch`, `compound`.
- Linux platform shim (xdotool / pactl / playerctl). Windows stubs.
- `sdac daemon --config <path> [--mock]` CLI verb.
- Device hotplug resilience + SIGINT/SIGTERM clean shutdown.

**Phase 2b — Service install + doctor**
- `sdac install-service` writes a systemd user unit + udev rule via sudo.
- `sdac uninstall-service` reverses; `--keep-udev` opt.
- `sdac doctor` reports device, libhidapi, python_deps, system_binaries, udev, service, config, and OBS reachability.

**Phase 3 — OBS integration**
- All 6 OBS action handlers execute via `obs-cmd` shell-out.
- `OBSClient` per host via `obsws-python` EventClient.
- Live state indicators: recording / streaming / replay / virtualcam / scene / input-mute keys re-render on OBS events.
- Daemon best-effort connects to each `obs_hosts` entry on startup; unreachable hosts log + skip.

**Phase 4 — Auto profile switching**
- Linux X11 active-window watcher via `python-xlib` polling `_NET_ACTIVE_WINDOW`.
- Windows watcher via pywin32 + psutil (ready for runtime verification on Windows).
- Daemon evaluates `profile_rules:` top-to-bottom on every window change; first match wins.
- Windows platform shim: real `send_chord`, `type_text`, `media_play/pause/next/prev` via `keybd_event`. `volume_*` stays `NotImplementedError` until Phase 4b.

### Deferred to Phase 4b

- Windows `sdac install-service` path (Task Scheduler at logon).
- pycaw integration for Windows volume control.

### Deferred to Phase 5b

- PyPI publish.
- ClawHub publish (if applicable).

### Tested

- 155 tests passing on Linux. ruff + mypy strict, clean.
- Real-hardware smoke verified end-to-end on a Stream Deck MK.2.

### Required runtime deps (Linux)

- `libhidapi-libusb0` — daemon fails to enumerate without it.
- `xdotool` — `key.chord` / `key.text`.
- `pactl` (pulseaudio-utils or pipewire-pulse) — `system.volume.*`.
- `playerctl` — `media.*`.
