# streamdeck-as-code

Cross-platform declarative driver for the Elgato Stream Deck. One YAML config produces identical behavior on Linux and Windows; later phases ship a daemon that talks to the device directly over USB HID with live OBS state integration.

**Status:** Phase 1 (current). `sdac validate` + `sdac preview` work without a USB device. Daemon, OBS integration, and Windows-specific watchers land in Phases 2-4.

## Phase 1 capabilities

- Validate a YAML config against the full v1 schema (Pydantic 2 discriminated union over 21 action types).
- Resolve `${ENV_VAR}` in any string field — keep passwords out of the YAML.
- Render every key in a profile/page as a single mosaic PNG. No USB device required.
- Warn (or strict-reject with `--strict-perms`) when the config file is world-readable on POSIX.

## Install

Recommended (pipx, isolated):

```bash
pipx install streamdeck-as-code
```

From source:

```bash
git clone https://github.com/solomonneas/streamdeck-as-code
cd streamdeck-as-code
pipx install --editable .
```

## Quick start

```bash
# 1. Write a config
$ cat > ~/.config/sdac/config.yaml <<'YAML'
version: 1
default_profile: coding
profiles:
  coding:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Tests", emoji: "🧪", bg: "#1e88e5"}
            action: {type: shell, cmd: "pnpm test"}
YAML

# 2. Validate
$ sdac validate ~/.config/sdac/config.yaml
OK: ~/.config/sdac/config.yaml (1 profile(s), 1 key(s) configured)

# 3. Preview as PNG (no device needed)
$ sdac preview ~/.config/sdac/config.yaml --out preview.png
Wrote preview.png (392x232)
```

See [`docs/schema.md`](docs/schema.md) for the full YAML reference.

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

Phase 1 validates these in the schema but only `sdac preview` executes (rendering icons). Actual key-press dispatch ships in Phase 2.

## Hardware

Phase 1 targets the Elgato Stream Deck MK.2 (15 keys, 72x72 JPEG per key). Architecture is hardware-agnostic; XL/Mini/Plus support is queued for a later phase.

## Development

```bash
git clone https://github.com/solomonneas/streamdeck-as-code
cd streamdeck-as-code
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
mypy src
pytest -q
```

Regenerate renderer goldens:

```bash
SDAC_REGEN=1 pytest tests/unit/test_render.py
git status tests/fixtures/goldens/  # inspect before committing
```

## License

MIT. See [LICENSE](LICENSE).
