# streamdeck-as-code — Design Spec

- **Status:** Draft (awaiting user review)
- **Date:** 2026-05-17
- **Owner:** Solomon
- **Hardware target (v1):** Elgato Stream Deck MK.2 (USB 0fd9:0080, 15 keys, 72×72 JPEG per key, firmware 4.40)
- **OS targets (v1):** Ubuntu 24.04 (the dev host), Windows 11 (the Windows host, laptop)

## Overview

A cross-platform daemon and CLI that drives an Elgato Stream Deck directly from a declarative YAML config. Both Linux and Windows run the same Python daemon talking to the device over USB HID. No Elgato official app, no StreamController — one process, one config, identical behavior on both hosts.

Primary use case is programming workflows (run tests, build, jump windows, paste snippets, git ops). Secondary use case is dev-streaming workflows: scene switching, recording, replay buffer, mute indicators — all driven through the existing obs-cmd LAN setup so a single Stream Deck can control OBS instances on any host on the home network.

Shipped as two public repos: `streamdeck-as-code` (the tool) and `my-streamdeck-config` (Solomon's personal config and a working example). pipx-installable, ClawHub package, GitHub releases.

## Goals

1. One YAML config produces identical behavior on Linux and Windows.
2. Hot reload on config change — no daemon restart needed.
3. Built-in integration with the existing `obs-cmd` multi-host setup. A button on a Linux-hosted Deck can control OBS on the Windows host and vice versa.
4. Action grammar covers programming (shell, key chords, text snippets, window control) and streaming (scenes, recording, mute, replay).
5. Live state on buttons — recording indicator lights up red when OBS is recording, mute button reflects actual mute state, etc.
6. Auto-profile-switching based on focused application (per-OS implementation).
7. Service install (systemd user unit on Linux, Task Scheduler entry on Windows).
8. Robust to device hotplug, OBS host disconnects, malformed config edits.
9. Shippable: pipx install, ClawHub publish, README following the 5-client setup pattern (per memory: `feedback-mcp-readme-five-clients`).

## Non-goals (v1)

- Stream Deck XL, Mini, Plus, Pedal, Neo support. Architecture leaves room; only MK.2 in v1.
- Macros recording UI.
- Web GUI for editing config.
- Built-in support for third-party plugins (Twitch chat overlays, Spotify, etc.) beyond what `shell` actions can do.
- Coexistence with Elgato's official Windows app running simultaneously (we replace it).
- macOS. Architecture should not preclude it but it's not in v1.

## Open questions / risks

- **Elgato Windows app coexistence:** if the user re-installs Elgato's app for another reason, both daemons will fight for the HID device. Mitigation: `sdac doctor` detects Elgato services and warns; `install-service` script stops/disables Elgato's service on Windows during install (with confirmation).
- **udev permissions on Linux:** currently device is reachable via GNOME session ACL (uaccess), but a system-level daemon (if user ever runs one) would need a proper udev rule. Decision: ship a udev rule install step that runs once via sudo.
- **State persistence across daemon restarts:** current page per profile, recent actions, etc. Decision for v1: ephemeral. Restart resets to each profile's `home` page. Add persistence in a later version if needed.
- **Active-window detection on Wayland:** Wayland blocks generic window-class introspection; ewmh works only on X11. the dev host runs X11 GNOME (confirmed via earlier xdotool-based dictation setup). Decision: X11-only on Linux for v1. Wayland support tracked as future work.

## Architecture

Single Python process per host:

```
              ┌───────────────────────────────────────────────┐
              │                 sdac daemon                   │
              │                                               │
  USB HID ◄──►│  device  ◄──►  renderer  ◄──►  profile/page  │
              │                                  state        │
              │     ▲                              ▲          │
              │     │                              │          │
              │  press dispatcher              event bus      │
              │     │                              ▲          │
              │     ▼                              │          │
              │   actions ─────► shell / key / obs / system / │
              │                  navigation                   │
              │     ▲                              ▲          │
              │     │                              │          │
              │  config loader ◄── watchdog        │          │
              │     ▲                              │          │
              │     │                       obs-ws clients    │
              │  config.yaml                       ▲          │
              └──────────────────────────────│─────│──────────┘
                                             │     │
                                       ┌─────┴───┐ │
                                       │ active  │ │
                                       │ window  │ │
                                       │ watcher │ │
                                       └─────────┘ │
                                                   ▼
                                    ┌──────────────────────────┐
                                    │ obs-websocket hosts (LAN)│
                                    │ roc, windows-host, laptop     │
                                    └──────────────────────────┘
```

### Components

**`sdac.device`** — USB HID I/O via `streamdeck` library (https://github.com/abcminiuser/python-elgato-streamdeck). MK.2 is supported upstream. Wraps device open/close, key press callbacks, key image push. Single-device assumption for v1 (multi-device deferred).

**`sdac.config`** — YAML parser, schema validator (Pydantic v2). Loads `~/.config/sdac/config.yaml` by default. Enforces mode 0600 (warn + refuse with `--strict-perms`, warn-only by default). Resolves `${ENV_VAR}` substitutions in string fields before validation, so passwords never appear in the validated model representation logged on error. Watches the file via `watchdog`. On reload, diffs the model and pushes only the changed keys to the device. Schema validation errors render an error icon on key 0 with notify, rather than crashing the daemon.

**`sdac.render`** — PIL-based icon renderer. Inputs: text + bg color + emoji + optional image path + state variant (idle/active/pressed/error/disconnected). Outputs: 72×72 JPEG bytes for the device. Caches by content hash. Supports dynamic icons (e.g., recording indicator rendered with a red dot when OBS is active).

**`sdac.actions`** — Registry of action types. Each action is a class with a typed parameter schema and an async `execute(context)` method. Built-in types listed in *Action grammar* below.

**`sdac.daemon`** — Orchestrator. Holds device, config, current profile/page, OBS clients, watchers. Receives key-press events from device, looks up the action for the current profile/page/key, dispatches asynchronously. Receives OBS events, updates state-bound key images. Receives active-window changes, switches profile if a rule matches.

**`sdac.obs`** — Thin async obs-websocket-5 client per configured host. Subscribes to events relevant to bound indicators (RecordStateChanged, StreamStateChanged, InputMuteStateChanged, CurrentProgramSceneChanged). Re-issues actions through `obs-cmd` for parity with the existing wrapper (decision: shell out to `obs-cmd` for actions, native websocket only for event subscription, to avoid duplicating auth logic).

**`sdac.watchers.active_window`** — Per-OS module.
- Linux (X11): `python-xlib` + ewmh to watch `_NET_ACTIVE_WINDOW` changes. Read `WM_CLASS` on each change.
- Windows: `pywin32` `GetForegroundWindow` polled every 250ms (or via SetWinEventHook for event-driven). Read process name via `GetWindowThreadProcessId` + `OpenProcess` + `GetModuleFileNameEx`.

**`sdac.cli`** — Click-based CLI. Commands:
- `sdac daemon [--config PATH]` — run foreground (default for systemd/scheduler invocation)
- `sdac validate [PATH]` — schema-check config
- `sdac preview [PATH] [--out preview.png]` — render the whole profile as one mosaic image, no device required
- `sdac doctor` — verify device, deps, permissions, OBS hosts reachable, conflicts (Elgato services, StreamController autostart)
- `sdac install-service` — systemd user unit (Linux) or Task Scheduler at-login (Windows). Idempotent.
- `sdac uninstall-service` — undo above
- `sdac version`

**`sdac.service`** — Install helpers. On Linux, drops `~/.config/systemd/user/sdac.service` and enables/starts via `systemctl --user`. Also installs the udev rule (`/etc/udev/rules.d/60-streamdeck.rules`) via sudo, prompting the user. On Windows, registers a Task Scheduler entry that runs `sdac daemon` at logon, restart on failure.

## YAML schema

```yaml
version: 1

# OBS instances accessible from this host.
# Passwords may be inlined (file must be mode 0600) OR use ${ENV_VAR} for indirection.
obs_hosts:
  roc:
    url: obsws://127.0.0.1:4455/${SDAC_OBS_ROC_PASS}
  windows-host:
    url: obsws://192.168.x.y:4455/${SDAC_OBS_windows-host_PASS}

# Auto-profile-switch rules (first match wins)
profile_rules:
  - profile: coding
    when:
      app_class: [code, jetbrains-idea-ce, ghostty]  # Linux WM_CLASS
      app_name:  [Code.exe, idea64.exe, WindowsTerminal.exe]  # Windows process name
  - profile: streaming
    when:
      app_class: [obs]
      app_name:  [obs64.exe]
  - profile: browsing
    when:
      app_class: [chromium, firefox]
      app_name:  [chrome.exe, firefox.exe]

default_profile: coding

# Variable substitution for actions (resolved per-host)
vars:
  active_repo_dir: ~/repos
  pnpm: /usr/bin/pnpm

profiles:
  coding:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Tests", emoji: "🧪", bg: "#1e88e5"}
            action: {type: shell, cmd: "cd {{vars.active_repo_dir}} && {{vars.pnpm}} test"}
          1:
            icon: {text: "Build", emoji: "🔨", bg: "#43a047"}
            action: {type: shell, cmd: "cd {{vars.active_repo_dir}} && {{vars.pnpm}} build"}
          2:
            icon: {text: "Git", emoji: "🌳", bg: "#6d4c41"}
            action: {type: page.go, page: git}
          14:
            icon: {text: "Stream", emoji: "🎥", bg: "#7b1fa2"}
            action: {type: profile.switch, profile: streaming}
      git:
        keys:
          0:
            icon: {text: "Back", emoji: "⬅️", bg: "#424242"}
            action: {type: page.go, page: home}
          1:
            icon: {text: "Status", emoji: "📋", bg: "#1e88e5"}
            action: {type: shell, cmd: "git -C {{vars.active_repo_dir}} status"}
          # ...

  streaming:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Cam", emoji: "📷", bg: "#1e88e5"}
            action:
              type: obs.scene.switch
              host: roc
              scene: "Camera"
          1:
            icon:
              text: "REC"
              bg_idle: "#424242"
              bg_active: "#d32f2f"
            indicator:
              bind: obs.recording.state
              host: roc
            action:
              type: obs.recording.toggle
              host: roc
          # ...
```

### Action grammar

| Action | Params | Behavior |
|---|---|---|
| `shell` | `cmd` (string), `cwd` (optional path), `shell` (default `bash` Linux / `pwsh` Windows) | Run command, capture exit. Failures render error variant for 2s. |
| `key.chord` | `keys` (e.g., `"ctrl+shift+t"`) | Send keystrokes. xdotool on Linux, SendKeys on Windows. |
| `key.text` | `text` (string) | Type literal text. |
| `open.url` | `url` | Open in default browser. |
| `open.app` | `path` or `name` | Launch application. |
| `obs.scene.switch` | `host`, `scene` | `obs-cmd -w obsws://… scene switch <scene>`. |
| `obs.recording.toggle` | `host` | `obs-cmd -w … recording toggle` (resolves to start/stop based on state). |
| `obs.streaming.toggle` | `host` | Same. |
| `obs.replay.save` | `host` | Save replay buffer. |
| `obs.virtualcam.toggle` | `host` | Toggle virtual cam. |
| `obs.input.mute.toggle` | `host`, `input_name` | Mute/unmute an audio input. |
| `system.volume.up` / `down` / `mute` | optional `step` | OS volume control. |
| `media.play` / `pause` / `next` / `prev` | — | OS media key. |
| `page.go` | `page` (string) | Navigate within current profile. |
| `profile.switch` | `profile` (string) | Manual profile switch (overrides auto rules for the rest of the session). |
| `compound` | `actions` (list) | Run a sequence. Stops on first failure unless `continue_on_error: true`. |

### Indicators (live state binding)

Buttons can bind their `active` icon variant to an OBS event source. The daemon subscribes once per host and re-renders affected keys when state changes.

| Bind | Event | True when |
|---|---|---|
| `obs.recording.state` | `RecordStateChanged` | output is `OBS_WEBSOCKET_OUTPUT_STARTED` or `STARTING` |
| `obs.streaming.state` | `StreamStateChanged` | similar |
| `obs.replay.state` | `ReplayBufferStateChanged` | started |
| `obs.virtualcam.state` | `VirtualcamStateChanged` | started |
| `obs.scene.current` | `CurrentProgramSceneChanged` | `scene` matches a configured value |
| `obs.input.muted` | `InputMuteStateChanged` | muted |

## Data flow

1. **Startup.** Daemon opens device, loads config, validates, connects to all configured OBS hosts (best-effort; failures logged, daemon stays up), starts active-window watcher, renders default profile/home page, attaches key-press callback.
2. **Key press.** Device fires callback → daemon looks up `profiles[active].pages[current].keys[i].action` → dispatches to action handler asynchronously → action result triggers state changes (e.g., page nav) → affected keys re-render.
3. **OBS event.** WebSocket message → match against indicator bindings → re-render keys whose state changed.
4. **Active window change.** Watcher fires → daemon evaluates `profile_rules` top-to-bottom → first match calls `profile.switch` internally.
5. **Config edit.** watchdog fires → daemon validates new config → if valid, diff vs current and push only changed keys → if invalid, log + render error icon on key 0 for 5s, keep current config.
6. **Device unplug.** Daemon detects HID error → renders nothing → polls for re-plug every 2s with backoff up to 30s → on re-plug, full re-render.

## Error handling / failure modes

| Failure | Behavior |
|---|---|
| Device disconnect | Daemon survives, re-renders on reconnect. No restart needed. |
| OBS host unreachable | Actions targeting that host fail with libnotify/BurntToast toast. Daemon stays up. State-bound icons render `disconnected` variant. |
| Config invalid on reload | Reject, log, render error overlay on key 0 for 5s, keep old config. |
| Action raises | Render `error` icon variant on the key for 2s, log the exception. |
| Renderer fails on a key | Log, fall back to plain text-only icon. |
| Daemon crashes | Service auto-restart (systemd `Restart=on-failure` / Task Scheduler restart-on-failure). |

## Testing strategy

- **Unit:** config schema (round-trip + invalid samples), icon rendering (golden images), action dispatcher (mock execute methods), indicator binding (state transition table).
- **Integration:** in-memory mock device that records image pushes and injects key presses. Drives end-to-end "press key 0 → shell action → exit 0 → idle icon" flows. No real USB.
- **Smoke:** `sdac doctor` runs in CI on Linux with a mock device fixture. Verifies all dependencies importable, schema compiles.
- **Manual:** a `tests/smoke-profile.yaml` exercises every built-in action type. Plug device, run daemon against this profile, press each key, verify expected outcome.
- **OBS integration:** integration tests stub the obs-websocket server with `obs-mock-server` (small helper to emit canned events on demand). State binding tests verify that a `RecordStateChanged` event re-renders the bound key.

## Packaging / distribution

- **PyPI:** `pip install streamdeck-as-code`. Console script `sdac`.
- **pipx:** primary recommended install path. `pipx install streamdeck-as-code`.
- **ClawHub:** mirror the PyPI package per the established pattern.
- **GitHub releases:** sdist + wheel attached to each tag.
- **Optional extras:**
  - `[obs]` — async websocket client (`obsws-python` or `simpleobsws`).
  - `[linux]` — `python-xlib`, `pydbus`, requires `xdotool` system package.
  - `[windows]` — `pywin32`.
- **Platform markers in pyproject** auto-install the right extras.
- **README:** follows the 5-client setup pattern (per Solomon's standing rule for AI/MCP-adjacent tools); for this tool the section is "Installing on each host" with concrete commands for Ubuntu + Windows.
- **License:** MIT.

## Repo structure

```
streamdeck-as-code/
  pyproject.toml
  README.md
  LICENSE
  CHANGELOG.md
  src/sdac/
    __init__.py
    __main__.py
    cli.py
    config.py
    device.py
    daemon.py
    render.py
    doctor.py
    service.py
    obs.py
    actions/
      __init__.py
      base.py
      shell.py
      key.py
      open.py
      obs.py
      system.py
      media.py
      navigation.py
    watchers/
      __init__.py
      active_window.py        # facade
      _linux.py               # X11 ewmh
      _windows.py             # User32 / pywin32
    assets/
      udev/60-streamdeck.rules
      systemd/sdac.service.template
      windows/sdac-task.xml.template
      fonts/                  # bundled font for rendering
  tests/
    unit/
    integration/
    fixtures/
      configs/
      icons/
    smoke-profile.yaml
  docs/
    superpowers/specs/2026-05-17-streamdeck-as-code-design.md  # this file
    schema.md
    actions.md
    installation.md
    development.md
  .github/workflows/
    ci.yml
    release.yml
```

Separate config repo:

```
my-streamdeck-config/
  config.yaml
  icons/                # custom image files referenced by config
  README.md             # explains the layout choices
  .gitignore            # never commit secrets — passwords/keys via env or sops
```

## Migration / rollout

1. **Phase 0 (this spec):** Approve direction.
2. **Phase 1 (foundation):** Repo init, pyproject, device + config + render modules, CLI scaffolding, unit tests. `sdac preview` works end-to-end. No daemon yet.
3. **Phase 2 (daemon + actions):** Daemon loop, built-in actions (shell, key, open, page.go, profile.switch). systemd install. Linux only.
4. **Phase 3 (OBS integration):** OBS action types, state-binding indicators, multi-host. Tested against the dev host OBS (live) and the Windows host OBS (live) over the LAN we just wired.
5. **Phase 4 (Windows port):** Windows watcher, Windows key sender, Task Scheduler install. Test on the Windows host.
6. **Phase 5 (polish + ship):** README, examples, `sdac doctor`, ClawHub publish, GitHub release v0.1.0.
7. **Phase 6 (config repo):** Solomon's `my-streamdeck-config` repo. Public. Real-world example of the tool.

Each phase is its own implementation plan (writing-plans skill produces them).

## Risks

- **Elgato Windows-app conflict.** Highest practical risk. Mitigation: doctor + install-service handle it explicitly. Documented.
- **udev permissions on Linux.** Currently only session-ACL grants access — if daemon runs at boot before login, fails. Mitigation: udev rule install step, plus systemd user unit (not system unit) so it starts at user session.
- **python-elgato-streamdeck maintenance.** Library is stable but lightly maintained. Vendor a tagged version into the lockfile; if it goes unmaintained, library is small enough to fork.
- **Scope creep.** Easy to chase XL/Plus/Mini support too early. Decision: MK.2 only in v1, architecture leaves room.
- **Wayland.** Future blocker for Linux active-window. Out of scope for v1 (the dev host is X11). Documented.
- **Cross-OS keysym mapping.** xdotool vs SendKeys syntax differ. Decision: define a neutral mini-grammar (`ctrl+shift+t`, `cmd+space`, etc.) translated per OS at the action layer.

## Decisions log

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Cross-platform Python daemon (no native drivers) | "Robust + open to it" per Solomon; eliminates Elgato app + StreamController parity work; same behavior on both OS. |
| Config format | YAML | Standard, comment-friendly, matches his other repos. |
| Schema validation | Pydantic v2 | Helpful errors, type-safe consumption downstream. |
| Language | Python | Best Stream Deck library (python-elgato-streamdeck), matches StreamController ecosystem, fast iteration. |
| OBS integration | Subscribe via native websocket, dispatch via shelling out to `obs-cmd` | Avoids re-implementing auth; reuses the multi-host wrapper we wired today. |
| Hardware support v1 | MK.2 only | Only model owned; XL/Plus/Mini deferred but architecture-clean. |
| OS support v1 | Ubuntu 24.04 X11 + Windows 11 | macOS not needed; Wayland deferred. |
| Service model | systemd user unit (Linux) / Task Scheduler at-login (Windows) | User-scoped device access; no privileged daemon needed. |
| Repo strategy | Two repos: `streamdeck-as-code` (tool) + `my-streamdeck-config` (Solomon's config) | Tool is reusable; config is personal example. |
| Visibility | Public, MIT, pipx + ClawHub + GitHub | Matches existing ship pattern. |

## What this is NOT

- A drop-in replacement for Elgato Stream Deck's "Multi Actions" GUI editor. v1 is YAML-only.
- A general HID device framework. Stream Deck specifically.
- A streaming app. It controls OBS; it doesn't stream.
