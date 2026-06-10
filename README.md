# deckctl

Cross-platform declarative driver for the Elgato Stream Deck. One YAML config produces identical behavior on Linux and Windows; the daemon talks to the device directly over USB HID with live OBS state integration.

**Status:** v0.3.1. `deckctl daemon` with the full action grammar, OBS integration + live indicators, auto profile switching, a bundled preset library (`deckctl init coding`, `streaming-twitch`, `streaming-youtube`), and systemd service install on Linux. The daemon and actions also run on Windows; autostart-at-login install (`deckctl install-service`) is Linux-only for now, with a Task Scheduler equivalent planned.

## Capabilities

- Validate a YAML config against the full v1 schema (Pydantic 2 discriminated union over 21 action types).
- Resolve `${ENV_VAR}` in any string field - keep passwords out of the YAML.
- Render every key in a profile/page as a single mosaic PNG (offline preview, no device required).
- Warn (or strict-reject with `--strict-perms`) when the config file is world-readable on POSIX.
- Run a daemon that owns a real Stream Deck MK.2 over USB and dispatches button presses to handlers.
- Hot-reload the config without restarting the daemon.
- Execute OBS actions over the LAN: scene switch, recording/streaming/replay/virtualcam toggle, audio mute.
- Live state indicators: keys bound to OBS recording/streaming/replay/scene/mute auto-update when OBS state changes.
- **Auto profile switching:** define `profile_rules:` matching `app_class` (Linux) or `app_name` (Windows); the daemon switches profiles when the focused window matches.
- Install as a systemd user unit with one command (`deckctl install-service`). Daemon autostarts at login.
- `deckctl doctor` reports on device, deps, service status, config, and OBS reachability - exits non-zero on any FAIL.

## Install

Recommended (pipx, isolated). The package is not on PyPI yet (publishing is planned), so install straight from the repo:

```bash
pipx install git+https://github.com/solomonneas/deckctl
```

From source:

```bash
git clone https://github.com/solomonneas/deckctl
cd deckctl
pipx install --editable .
```

### Linux runtime dependencies

Several actions shell out to system utilities. On Ubuntu / Debian:

```bash
sudo apt install -y libhidapi-libusb0 xdotool playerctl
# pactl ships with pulseaudio-utils on PulseAudio or pipewire-pulse on PipeWire
```

`libhidapi-libusb0` is the USB HID library the `streamdeck` Python package binds to; the daemon will fail to enumerate any device without it. `xdotool` is required for `key.chord` and `key.text` actions, `pactl` for `system.volume.*`, `playerctl` for `media.*` - those three are only invoked at action dispatch time, so the daemon starts without them, but pressing an action that needs one will fail with `FileNotFoundError`.

## Quick start

```bash
# 1. Install + a starter config in one shot (not on PyPI yet, install from the repo)
pipx install git+https://github.com/solomonneas/deckctl
deckctl init coding   # or `default`, `streaming-twitch`, `streaming-youtube`
deckctl init --list   # see all available presets

# 2. Validate (no device required)
deckctl validate ~/.config/deckctl/config.yaml

# 3. Preview as PNG (no device required)
deckctl preview ~/.config/deckctl/config.yaml --out preview.png

# 4. Run the daemon
deckctl daemon --config ~/.config/deckctl/config.yaml -v
```

See [`docs/schema.md`](docs/schema.md) for the full YAML reference.

## Daemon

Run the daemon against a plugged-in Stream Deck MK.2:

```bash
deckctl daemon --config ~/.config/deckctl/config.yaml -v
```

Or against an in-memory mock device (no hardware required - useful for testing your config):

```bash
deckctl daemon --config ~/.config/deckctl/config.yaml --mock -v
```

The daemon stays in the foreground. Use `Ctrl+C` to stop. To autostart it at login instead, see the next section.

Edit the config file while the daemon is running - it'll hot-reload within ~1s. Invalid configs are logged and rejected; the daemon keeps the previous valid config.

## Install as a service (Linux)

Once your config works the way you want via `deckctl daemon`, register it as a systemd user unit so it autostarts at login:

```bash
deckctl install-service --config ~/.config/deckctl/config.yaml
```

This:
1. Writes `~/.config/systemd/user/deckctl.service` pointing at your config.
2. Installs `/etc/udev/rules.d/60-streamdeck.rules` via `sudo` (prompts once for your password) so the device is reachable to any logged-in user - needed for the unit to find the Deck at boot.
3. Reloads udev, daemon-reloads systemd, enables and starts the service.

To stop and remove:

```bash
deckctl uninstall-service        # removes systemd unit AND udev rule (sudo)
deckctl uninstall-service --keep-udev   # leaves the udev rule in place
```

Health check at any time:

```bash
deckctl doctor                                      # full report
deckctl doctor --config ~/.config/deckctl/config.yaml  # also validates the config
```

Output is a tabular `PASS / WARN / FAIL` per check (device, libhidapi, python_deps, system_binaries, udev, service, config). Exit code is non-zero if any check fails.

## OBS integration

Configure one or more OBS instances under `obs_hosts:` in your config, then any `obs.*` action can target them by name:

```yaml
obs_hosts:
  roc:
    url: obsws://127.0.0.1:4455/${OBS_ROC_PASS}
  windows-host:
    url: obsws://192.168.x.y:4455/${OBS_windows-host_PASS}

profiles:
  streaming:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Cam", bg: "#1e88e5"}
            action: {type: obs.scene.switch, host: roc, scene: "Camera"}
          1:
            icon:
              text: "REC"
              bg_idle: "#424242"
              bg_active: "#d32f2f"
            indicator: {bind: obs.recording.state, host: roc}
            action: {type: obs.recording.toggle, host: roc}
```

Actions execute via `obs-cmd` on PATH. The daemon also opens a WebSocket connection to each `obs_hosts` entry on startup to subscribe to state events; the REC key above turns red when OBS is actually recording, and back to gray when it stops. Hosts that aren't reachable at daemon startup are logged and skipped - actions targeting them will simply fail at dispatch time.

Indicators support:
- `obs.recording.state`, `obs.streaming.state`, `obs.replay.state`, `obs.virtualcam.state` - boolean output states
- `obs.scene.current` - match a `scene:` name; key is active when that scene is the current program scene
- `obs.input.muted` - match an `input_name:`; key is active when that audio input is muted

## Auto profile switching

Add `profile_rules:` to your config to switch profiles automatically when the focused application changes:

```yaml
profile_rules:
  - profile: streaming
    when:
      app_class: [obs]            # Linux WM_CLASS (lowercased)
      app_name:  [obs64.exe]      # Windows process basename (lowercased)
  - profile: coding
    when:
      app_class: [code, jetbrains-idea-ce, ghostty]
      app_name:  [code.exe, idea64.exe, windowsterminal.exe]
  - profile: browsing
    when:
      app_class: [chromium, firefox]
      app_name:  [chrome.exe, firefox.exe]

default_profile: coding
```

Rules are evaluated top-to-bottom; the first match wins. Linux uses X11's `_NET_ACTIVE_WINDOW` + `WM_CLASS`; Windows uses `GetForegroundWindow` + the process basename. Both poll every 250ms - fast enough to feel instant. Wayland is not supported yet (the daemon falls back to "no auto-switch" if it can't open an X display).

## Action grammar (v1)

| Action | Purpose |
|---|---|
| `shell` | Run a shell command. |
| `key.chord` | Send a keystroke (e.g., `ctrl+shift+t`). |
| `key.text` | Type literal text. |
| `open.url` / `open.app` | Launch a URL / app. |
| `obs.scene.switch`, `obs.recording.toggle`, `obs.streaming.toggle`, `obs.replay.save`, `obs.virtualcam.toggle`, `obs.input.mute.toggle` | OBS WebSocket actions (target any host on the LAN). |
| `system.volume.up` / `.down` / `.mute` | OS volume control. |
| `media.play` / `.pause` / `.next` / `.prev` | OS media keys. |
| `page.go` | Navigate within a profile. |
| `profile.switch` | Switch active profile manually. |
| `compound` | Sequence of actions. |

All of these are validated by `deckctl validate` and dispatched live by `deckctl daemon`. `deckctl preview` renders the icons without touching a device.

## Hardware

deckctl targets the Elgato Stream Deck MK.2 (15 keys, 72x72 JPEG per key). Architecture is hardware-agnostic; XL/Mini/Plus support is planned.

## Development

```bash
git clone https://github.com/solomonneas/deckctl
cd deckctl
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
mypy src
pytest -q
```

Regenerate renderer goldens:

```bash
DECKCTL_REGEN=1 pytest tests/unit/test_render.py
git status tests/fixtures/goldens/  # inspect before committing
```

## License

MIT. See [LICENSE](LICENSE).
