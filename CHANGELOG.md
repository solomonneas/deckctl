# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Linux: X11 active-window watcher no longer floods syslog when the display socket dies.** `ConnectionClosedError` now stops the watcher with a single warning, unavailable displays disable the watcher cleanly, and other poll errors are rate-limited instead of logging full stack traces every 250ms.

## [0.3.1] - 2026-05-18

### Fixed

- **Windows: AUTO key was unusable.** `_vk_for()` in `platform/_windows.py` only handled modifiers and single-character tokens, so any chord using a named special key (Return, Tab, Escape, arrows, F1-F12) raised `ValueError` and aborted the keystroke. The AUTO key in every bundled preset uses `Return`, so on Windows it failed silently every press. Added a `_VK_SPECIAL` map covering the common named keys and moved `import win32api` into the single-char fallback so the module is importable on Linux for unit tests.
- **`coding` preset: terminal sub-page was unreachable.** Home key 9 was wired to open slack.com, leaving the `terminal` sub-page (defined in the same preset) with no entry point. Replaced with a `Term` key that runs `page.go: terminal`.
- **`deckctl init` no longer ignores `XDG_CONFIG_HOME`.** Default destination now resolves from `$XDG_CONFIG_HOME/deckctl/config.yaml` when set, falling back to `~/.config/deckctl/config.yaml` otherwise. Matches XDG Base Directory spec.
- **`deckctl init` write is now atomic (no force).** Switched from check-then-write to `Path.open("x")` exclusive create. Closes the TOCTOU window between the existence check and the write where two `deckctl init` calls (or any other process) could race and clobber an existing config.

### Internal

- Added `tests/unit/test_platform_windows.py` covering `_vk_for` named keys, modifiers, single-char fallback, and the AUTO key chord token.
- Added 3 new `init` tests for XDG_CONFIG_HOME resolution, the home-fallback path, and exclusive-create semantics.
- Set `encoding="utf-8"` on the remaining `Path.write_text` call in `test_presets.py` so the suite runs cleanly under Windows cp1252.
- Scrubbed em dashes and en dashes from all public docs, source, and tests to match the project writing style.

## [0.3.0] - 2026-05-18

### Added

- **Preset library + `deckctl init <preset>`** - bundled YAMLs you can drop into your config with one command:
  - `default` (3-key smoke layout)
  - `coding` (dev workflow with 5 pages: home, git, snippets, terminal, scripts; includes Claude + Codex launch buttons)
  - `streaming-twitch` (15 keys: 5 OBS scenes, record/stream/replay/virtual-cam toggles with live indicators, mic mute, Twitch chat + dashboard)
  - `streaming-youtube` (same shape as Twitch with YouTube Studio + chat URLs)
- Every preset includes an **AUTO** key on the bottom-right that types an autonomous-mode trigger phrase + Enter into the focused terminal/Claude prompt.
- `deckctl init --list` shows available presets and one-line descriptions.
- `deckctl init <name> [--to PATH] [--force]` writes the chosen preset.

### Notes

- No schema changes, no new action types. All presets use the existing v1 schema. Existing configs continue to work unchanged.
- Streaming presets require `DECKCTL_OBS_LOCAL_PASS` in the environment before running the daemon (paste from OBS > Tools > WebSocket Server Settings).
- Claude/Codex launch buttons in the coding preset use `x-terminal-emulator` (Debian/Ubuntu alternatives entry). On other distros, edit the shell.cmd to your terminal of choice.

## [0.2.0] - 2026-05-18

### Changed (breaking)

- **Project renamed from `streamdeck-as-code` to `deckctl`.**
- Binary renamed from `sdac` to `deckctl`. Old `sdac` command no longer exists.
- Python package renamed from `sdac` to `deckctl`. All imports change: `from sdac.X` → `from deckctl.X`.
- Distribution name on PyPI is now `deckctl`. Install with `pipx install deckctl`.
- Env-var prefix renamed: `SDAC_REGEN`, `SDAC_TEST_OBS_PASS` → `DECKCTL_REGEN`, `DECKCTL_TEST_OBS_PASS`.
- systemd unit renamed: `sdac.service` → `deckctl.service`. Run `deckctl uninstall-service` on v0.1.0 then `deckctl install-service` on v0.2.0 to migrate.
- GitHub repo URL: `github.com/solomonneas/streamdeck-as-code` redirects to `github.com/solomonneas/deckctl`.

### Compatibility

- YAML config schema is unchanged. Existing v0.1.0 configs work as-is.
- v0.1.0 wheels at the old release URL still install via the GitHub redirect.

## [0.1.0] - 2026-05-17

Initial public release. Covers Phase 1 through Phase 4 of the implementation roadmap
(see `docs/superpowers/specs/2026-05-17-deckctl-design.md`).

### Added

**Phase 1 - Foundation**
- Pydantic v2 schema for the YAML config (discriminated union over 21 action types).
- `${ENV_VAR}` substitution across the entire parsed YAML tree.
- POSIX file permission check (`--strict-perms`).
- `deckctl validate <config>` CLI verb.
- Pillow + Pilmoji icon renderer (text, emoji, image-background, state variants).
- `deckctl preview <config>` CLI verb - renders the full profile as a mosaic PNG.
- Bundled rsms/inter v4.0 Inter-Bold.ttf for deterministic icon rendering.
- GitHub Actions CI on Ubuntu + Windows, Python 3.11 + 3.12.

**Phase 2a - Daemon + actions**
- USB HID I/O via `python-elgato-streamdeck` for Stream Deck MK.2.
- Cross-platform `Device` protocol with `MockDevice` for tests.
- Synchronous threaded daemon, hot-reload via `watchdog`.
- Built-in action handlers: `shell`, `key.chord`, `key.text`, `open.url`, `open.app`, `system.volume.up/down/mute`, `media.play/pause/next/prev`, `page.go`, `profile.switch`, `compound`.
- Linux platform shim (xdotool / pactl / playerctl). Windows stubs.
- `deckctl daemon --config <path> [--mock]` CLI verb.
- Device hotplug resilience + SIGINT/SIGTERM clean shutdown.

**Phase 2b - Service install + doctor**
- `deckctl install-service` writes a systemd user unit + udev rule via sudo.
- `deckctl uninstall-service` reverses; `--keep-udev` opt.
- `deckctl doctor` reports device, libhidapi, python_deps, system_binaries, udev, service, config, and OBS reachability.

**Phase 3 - OBS integration**
- All 6 OBS action handlers execute via `obs-cmd` shell-out.
- `OBSClient` per host via `obsws-python` EventClient.
- Live state indicators: recording / streaming / replay / virtualcam / scene / input-mute keys re-render on OBS events.
- Daemon best-effort connects to each `obs_hosts` entry on startup; unreachable hosts log + skip.

**Phase 4 - Auto profile switching**
- Linux X11 active-window watcher via `python-xlib` polling `_NET_ACTIVE_WINDOW`.
- Windows watcher via pywin32 + psutil (ready for runtime verification on Windows).
- Daemon evaluates `profile_rules:` top-to-bottom on every window change; first match wins.
- Windows platform shim: real `send_chord`, `type_text`, `media_play/pause/next/prev` via `keybd_event`. `volume_*` stays `NotImplementedError` until Phase 4b.

### Deferred to Phase 4b

- Windows `deckctl install-service` path (Task Scheduler at logon).
- pycaw integration for Windows volume control.

### Deferred to Phase 5b

- PyPI publish.
- ClawHub publish (if applicable).

### Tested

- 155 tests passing on Linux. ruff + mypy strict, clean.
- Real-hardware smoke verified end-to-end on a Stream Deck MK.2.

### Required runtime deps (Linux)

- `libhidapi-libusb0` - daemon fails to enumerate without it.
- `xdotool` - `key.chord` / `key.text`.
- `pactl` (pulseaudio-utils or pipewire-pulse) - `system.volume.*`.
- `playerctl` - `media.*`.
