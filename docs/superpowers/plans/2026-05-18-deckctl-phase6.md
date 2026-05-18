# deckctl Phase 6 Implementation Plan — Preset library + `deckctl init`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 4 bundled YAML presets (`default`, `coding` with 5 pages, `streaming-twitch`, `streaming-youtube`) plus a `deckctl init <preset>` CLI verb that writes the chosen preset to `~/.config/deckctl/config.yaml`. Bump to v0.3.0.

**Architecture:** New `deckctl.presets` package with two helpers (`list_presets()`, `get_preset(name)`) backed by `importlib.resources` reading bundled YAML. New Click command `init` in `deckctl.cli`. Each bundled YAML is validated against the existing Pydantic schema via a parameterized test. No schema changes, no new action types, no new runtime deps. Additive only.

**Tech Stack:** Python 3.12, Click, Pydantic (existing schema), pytest, `importlib.resources`.

---

## File Structure

```
streamdeck-as-code/
  pyproject.toml                              # Modify: bump version 0.2.0 → 0.3.0
  src/deckctl/
    __init__.py                               # Modify: __version__ → 0.3.0
    cli.py                                    # Modify: add `init` command
    presets/
      __init__.py                             # NEW: list_presets() + get_preset() + DESCRIPTIONS
      default.yaml                            # NEW: 3-key smoke preset
      coding.yaml                             # NEW: dev workflow, 5 pages × 15 keys
      streaming-twitch.yaml                   # NEW: Twitch streaming, 1 page × 15 keys
      streaming-youtube.yaml                  # NEW: YouTube streaming, 1 page × 15 keys
  tests/unit/
    test_presets.py                           # NEW: loader + parameterized schema validation
    test_cli.py                               # Modify: add init verb tests
  CHANGELOG.md                                # Modify: add v0.3.0 section
  README.md                                   # Modify: update status + Quick start with deckctl init
```

**Boundary contracts:**
- `deckctl.presets.get_preset(name)` returns raw YAML *text* (str). Schema parsing happens at the caller via the existing `load_config`.
- The CLI `init` command is the only writer to the user's config path. Tests use `--to` to redirect to tmp paths.

---

## Task 1: Presets package scaffolding + loader

**Files:**
- Create: `src/deckctl/presets/__init__.py`
- Create: `tests/unit/test_presets.py`

- [ ] **Step 1: Write failing test — `tests/unit/test_presets.py`**

```python
"""Tests for deckctl.presets: the loader, the list, and per-preset schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from deckctl.presets import DESCRIPTIONS, get_preset, list_presets


def test_list_presets_returns_dict_of_name_to_description():
    presets = list_presets()
    assert isinstance(presets, dict)
    # Subsequent tasks add more entries; for Task 1 we just verify the shape.
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in presets.items())


def test_descriptions_dict_is_the_source_of_truth():
    """list_presets() should return DESCRIPTIONS as-is."""
    assert list_presets() == DESCRIPTIONS


def test_get_preset_unknown_name_raises_key_error():
    with pytest.raises(KeyError, match="unknown preset"):
        get_preset("nonexistent")
```

- [ ] **Step 2: Run failing**

```bash
cd ~/repos/streamdeck-as-code
. .venv/bin/activate
pytest tests/unit/test_presets.py -v
```

Expected: ImportError on `deckctl.presets`.

- [ ] **Step 3: Write `src/deckctl/presets/__init__.py`**

```python
"""Bundled YAML presets accessible via `deckctl init <name>`.

Each preset is a complete config file shipped as package data. The CLI's
`init` command reads one via `get_preset()` and writes it to the user's
config path.

Adding a new preset:
1. Drop the YAML file next to this module (e.g. `myproject.yaml`).
2. Add an entry to DESCRIPTIONS below.
3. The parameterized schema-validation test in tests/unit/test_presets.py
   picks it up automatically and fails the build if the YAML doesn't validate.
"""

from __future__ import annotations

from importlib.resources import files

DESCRIPTIONS: dict[str, str] = {}


def list_presets() -> dict[str, str]:
    """Return the available presets as {name: one-line-description}."""
    return DESCRIPTIONS


def get_preset(name: str) -> str:
    """Return the raw YAML text for the named preset.

    Raises KeyError if the preset is not in DESCRIPTIONS.
    """
    if name not in DESCRIPTIONS:
        raise KeyError(f"unknown preset {name!r} (available: {sorted(DESCRIPTIONS)})")
    return files("deckctl.presets").joinpath(f"{name}.yaml").read_text()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_presets.py -v
```

Expected: 3 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 158 tests passing (155 prior + 3 new).

- [ ] **Step 6: Commit**

```bash
git add src/deckctl/presets/__init__.py tests/unit/test_presets.py
git commit -m "feat(presets): scaffolding + loader API"
```

---

## Task 2: `default` preset (3-key smoke)

**Files:**
- Create: `src/deckctl/presets/default.yaml`
- Modify: `src/deckctl/presets/__init__.py` (add to DESCRIPTIONS)
- Modify: `tests/unit/test_presets.py` (add parameterized schema test)

- [ ] **Step 1: Write the preset — `src/deckctl/presets/default.yaml`**

```yaml
# deckctl default preset — minimal 3-key smoke layout.
# Use after first install to verify everything works, then edit or replace
# with a richer preset like `deckctl init coding`.

version: 1
default_profile: default

profiles:
  default:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon:
              text: "Hello"
              emoji: "👋"
              bg: "#1e88e5"
            action:
              type: shell
              cmd: "notify-send 'deckctl' 'hello from key 0' || echo 'hello from key 0'"
          7:
            icon:
              text: "Type"
              emoji: "⌨️"
              bg: "#43a047"
            action:
              type: key.text
              text: "deckctl works"
          14:
            icon:
              text: "AUTO"
              emoji: "🤖"
              bg: "#1565c0"
              fg: "#ffffff"
            action:
              type: compound
              actions:
                - type: key.text
                  text: "defer to your decisions, scope/plan/execute autonomously, skip the question loop"
                - type: key.chord
                  keys: "Return"
```

- [ ] **Step 2: Register the preset in `DESCRIPTIONS`**

In `src/deckctl/presets/__init__.py`, replace the empty `DESCRIPTIONS` dict with:

```python
DESCRIPTIONS: dict[str, str] = {
    "default": "Minimal 3-key smoke layout. Use after install to verify everything works.",
}
```

- [ ] **Step 3: Add parameterized schema-validation test**

Append to `tests/unit/test_presets.py`:

```python
@pytest.mark.parametrize("name", list(DESCRIPTIONS))
def test_bundled_preset_validates_against_schema(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every bundled preset must load cleanly through the production schema."""
    # Streaming presets reference ${DECKCTL_OBS_LOCAL_PASS}; set a dummy value
    # so env-var substitution succeeds. (Schema doesn't care about the value.)
    monkeypatch.setenv("DECKCTL_OBS_LOCAL_PASS", "test-password-not-used")

    from deckctl.config import load_config

    raw = get_preset(name)
    p = tmp_path / f"{name}.yaml"
    p.write_text(raw)

    cfg = load_config(p)
    assert cfg.version == 1
    assert cfg.default_profile in cfg.profiles


def test_get_preset_returns_text_for_known_name():
    """Sanity check the loader actually returns YAML content."""
    text = get_preset("default")
    assert "version: 1" in text
    assert "profiles:" in text
```

(The `@pytest.mark.parametrize("name", list(DESCRIPTIONS))` reads the dict at collection time, so every new entry auto-runs.)

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_presets.py -v
```

Expected: 5 passing (3 from Task 1 + 1 schema validation for `default` + 1 loader return check).

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 160 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/deckctl/presets/default.yaml src/deckctl/presets/__init__.py tests/unit/test_presets.py
git commit -m "feat(presets): default 3-key smoke preset"
```

---

## Task 3: `coding` preset (5 pages × 15 keys)

**Files:**
- Create: `src/deckctl/presets/coding.yaml`
- Modify: `src/deckctl/presets/__init__.py` (DESCRIPTIONS)

- [ ] **Step 1: Write the preset — `src/deckctl/presets/coding.yaml`**

```yaml
# deckctl coding preset — dev workflow with 5 pages.
#
# Pages: home → git → snippets → terminal → scripts (use page.go to navigate;
# each sub-page's key 14 is "Back" to home).
#
# Customize:
# - Claude (key 5) and Codex (key 6) on home page launch a new terminal via
#   `x-terminal-emulator` (Debian/Ubuntu standard). If your distro doesn't ship
#   that alternatives entry, swap to `gnome-terminal`, `kitty`, `alacritty`,
#   `wezterm`, or `xterm` in those keys' shell.cmd.
# - The `coding.scripts` page is mostly placeholders pointing at ~/scripts/*.sh.
#   Either create those scripts or edit each key's action.cmd to your real paths.
# - To use the real Anthropic/OpenAI logos instead of emoji + brand-color icons,
#   drop PNGs at ~/.config/deckctl/icons/{claude,codex}.png and change the icon
#   sections to `{image: "~/.config/deckctl/icons/claude.png"}`.

version: 1
default_profile: coding

vars:
  pnpm: pnpm

profiles:
  coding:
    default_page: home
    pages:

      home:
        keys:
          0:
            icon: {text: "Tests", emoji: "🧪", bg: "#1e88e5"}
            action: {type: shell, cmd: "{{vars.pnpm}} test"}
          1:
            icon: {text: "Build", emoji: "🔨", bg: "#43a047"}
            action: {type: shell, cmd: "{{vars.pnpm}} build"}
          2:
            icon: {text: "Lint", emoji: "✨", bg: "#7b1fa2"}
            action: {type: shell, cmd: "{{vars.pnpm}} lint --fix"}
          3:
            icon: {text: "Git", emoji: "🌳", bg: "#6d4c41"}
            action: {type: page.go, page: git}
          4:
            icon: {text: "Snip", emoji: "📝", bg: "#5d4037"}
            action: {type: page.go, page: snippets}
          5:
            icon: {text: "Claude", emoji: "✨", bg: "#cc785c", fg: "#ffffff"}
            action:
              type: shell
              cmd: 'setsid x-terminal-emulator -e bash -lc "claude --permission-mode bypassPermissions; exec bash" </dev/null >/dev/null 2>&1 &'
          6:
            icon: {text: "Codex", emoji: "🤖", bg: "#10a37f", fg: "#ffffff"}
            action:
              type: shell
              cmd: 'setsid x-terminal-emulator -e bash -lc "codex --yolo; exec bash" </dev/null >/dev/null 2>&1 &'
          7:
            icon: {text: "VS Code", emoji: "🎨", bg: "#0078d4"}
            action: {type: open.app, name: code}
          8:
            icon: {text: "Local", emoji: "🌐", bg: "#1976d2"}
            action: {type: open.url, url: "http://localhost:3000"}
          9:
            icon: {text: "Slack", emoji: "💬", bg: "#4a154b"}
            action: {type: open.url, url: "https://slack.com"}
          10:
            icon: {text: "Scripts", emoji: "📂", bg: "#455a64"}
            action: {type: page.go, page: scripts}
          11:
            icon: {text: "Vol-", emoji: "🔉", bg: "#37474f"}
            action: {type: system.volume.down, step: 5}
          12:
            icon: {text: "Mute", emoji: "🔇", bg: "#37474f"}
            action: {type: system.volume.mute}
          13:
            icon: {text: "Vol+", emoji: "🔊", bg: "#37474f"}
            action: {type: system.volume.up, step: 5}
          14:
            icon: {text: "AUTO", emoji: "🤖", bg: "#1565c0", fg: "#ffffff"}
            action:
              type: compound
              actions:
                - {type: key.text, text: "defer to your decisions, scope/plan/execute autonomously, skip the question loop"}
                - {type: key.chord, keys: "Return"}

      git:
        keys:
          0:
            icon: {text: "Status", emoji: "📋", bg: "#1e88e5"}
            action: {type: shell, cmd: "git status"}
          1:
            icon: {text: "Add all", emoji: "➕", bg: "#43a047"}
            action: {type: shell, cmd: "git add -A"}
          2:
            icon: {text: "Commit", emoji: "💾", bg: "#fb8c00"}
            action: {type: shell, cmd: "git commit"}
          3:
            icon: {text: "Quick c", emoji: "✏️", bg: "#fb8c00"}
            action:
              type: key.text
              text: 'git commit -m ""'
          4:
            icon: {text: "Push", emoji: "⬆️", bg: "#d32f2f"}
            action: {type: shell, cmd: "git push"}
          5:
            icon: {text: "Pull", emoji: "⬇️", bg: "#7b1fa2"}
            action: {type: shell, cmd: "git pull --rebase"}
          6:
            icon: {text: "Log", emoji: "📜", bg: "#455a64"}
            action: {type: shell, cmd: "git log --oneline -20"}
          7:
            icon: {text: "Diff", emoji: "👀", bg: "#455a64"}
            action: {type: shell, cmd: "git diff"}
          8:
            icon: {text: "Staged", emoji: "📦", bg: "#455a64"}
            action: {type: shell, cmd: "git diff --staged"}
          9:
            icon: {text: "Branch", emoji: "🌿", bg: "#388e3c"}
            action: {type: shell, cmd: "git branch -vv"}
          10:
            icon: {text: "New br", emoji: "✨", bg: "#388e3c"}
            action: {type: key.text, text: "git checkout -b "}
          11:
            icon: {text: "Main", emoji: "🏠", bg: "#1976d2"}
            action: {type: shell, cmd: "git checkout main && git pull --rebase"}
          12:
            icon: {text: "Stash", emoji: "📥", bg: "#6d4c41"}
            action: {type: shell, cmd: "git stash"}
          13:
            icon: {text: "Pop", emoji: "📤", bg: "#6d4c41"}
            action: {type: shell, cmd: "git stash pop"}
          14:
            icon: {text: "Back", emoji: "⬅️", bg: "#424242"}
            action: {type: page.go, page: home}

      snippets:
        keys:
          0:
            icon: {text: "log()", emoji: "📋", bg: "#1e88e5"}
            action: {type: key.text, text: "console.log()"}
          1:
            icon: {text: "print()", emoji: "🐍", bg: "#1976d2"}
            action: {type: key.text, text: "print()"}
          2:
            icon: {text: "TODO", emoji: "📝", bg: "#fb8c00"}
            action: {type: key.text, text: "# TODO: "}
          3:
            icon: {text: "FIXME", emoji: "🚨", bg: "#d32f2f"}
            action: {type: key.text, text: "# FIXME: "}
          4:
            icon: {text: "test", emoji: "🧪", bg: "#43a047"}
            action: {type: key.text, text: 'it("", () => {})'}
          5:
            icon: {text: "import", emoji: "📦", bg: "#7b1fa2"}
            action: {type: key.text, text: "import { } from ''"}
          6:
            icon: {text: "async", emoji: "🔄", bg: "#0288d1"}
            action: {type: key.text, text: "async function ", }
          7:
            icon: {text: "try", emoji: "🛡️", bg: "#fb8c00"}
            action: {type: key.text, text: "try {\n} catch (err) {\n}"}
          8:
            icon: {text: "arrow", emoji: "➡️", bg: "#5d4037"}
            action: {type: key.text, text: "() => "}
          9:
            icon: {text: "Please", emoji: "🙏", bg: "#1565c0"}
            action: {type: key.text, text: "Please "}
          10:
            icon: {text: "---", emoji: "➖", bg: "#455a64"}
            action: {type: key.text, text: "\n---\n"}
          11:
            icon: {text: "===", emoji: "🟰", bg: "#455a64"}
            action: {type: key.text, text: "\n===\n"}
          12:
            icon: {text: "x-uuid", emoji: "🔑", bg: "#6d4c41"}
            action: {type: shell, cmd: "uuidgen | tr -d '\\n' | xclip -selection clipboard"}
          13:
            icon: {text: "x-date", emoji: "📅", bg: "#6d4c41"}
            action: {type: shell, cmd: "date '+%Y-%m-%d %H:%M:%S' | tr -d '\\n' | xclip -selection clipboard"}
          14:
            icon: {text: "Back", emoji: "⬅️", bg: "#424242"}
            action: {type: page.go, page: home}

      terminal:
        keys:
          0:
            icon: {text: "New W", emoji: "➕", bg: "#43a047"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "c"}
          1:
            icon: {text: "Prev W", emoji: "⬅️", bg: "#1976d2"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "p"}
          2:
            icon: {text: "Next W", emoji: "➡️", bg: "#1976d2"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "n"}
          3:
            icon: {text: "Split |", emoji: "🪟", bg: "#455a64"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "shift+5"}
          4:
            icon: {text: "Split -", emoji: "🪟", bg: "#455a64"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "shift+apostrophe"}
          5:
            icon: {text: "P Up", emoji: "⬆️", bg: "#37474f"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "Up"}
          6:
            icon: {text: "P Down", emoji: "⬇️", bg: "#37474f"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "Down"}
          7:
            icon: {text: "P Left", emoji: "⬅️", bg: "#37474f"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "Left"}
          8:
            icon: {text: "P Right", emoji: "➡️", bg: "#37474f"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "Right"}
          9:
            icon: {text: "Zoom", emoji: "🔍", bg: "#7b1fa2"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "z"}
          10:
            icon: {text: "Detach", emoji: "📤", bg: "#fb8c00"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "d"}
          11:
            icon: {text: "Session", emoji: "📋", bg: "#1565c0"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "s"}
          12:
            icon: {text: "Kill P", emoji: "💀", bg: "#b71c1c"}
            action:
              type: compound
              actions:
                - {type: key.chord, keys: "ctrl+b"}
                - {type: key.chord, keys: "x"}
          13:
            icon: {text: "Clear", emoji: "🧹", bg: "#455a64"}
            action: {type: key.chord, keys: "ctrl+l"}
          14:
            icon: {text: "Back", emoji: "⬅️", bg: "#424242"}
            action: {type: page.go, page: home}

      # coding.scripts — quick launchers for personal scripts.
      # Placeholder keys point at ~/scripts/*.sh paths. Either create those
      # scripts, or edit each key's action.cmd to point at where your scripts
      # actually live. Tip: keep ~/scripts/ on PATH so you can invoke by
      # name from terminals too.
      scripts:
        keys:
          0:
            icon: {text: "Deploy", emoji: "🚀", bg: "#d32f2f"}
            action: {type: shell, cmd: "~/scripts/deploy.sh"}
          1:
            icon: {text: "Seed", emoji: "🌱", bg: "#43a047"}
            action: {type: shell, cmd: "~/scripts/seed.sh"}
          2:
            icon: {text: "Clean", emoji: "🧹", bg: "#455a64"}
            action: {type: shell, cmd: "~/scripts/clean.sh"}
          3:
            icon: {text: "Restart", emoji: "🔄", bg: "#fb8c00"}
            action: {type: shell, cmd: "~/scripts/restart.sh"}
          4:
            icon: {text: "Stats", emoji: "📊", bg: "#1565c0"}
            action: {type: shell, cmd: "~/scripts/stats.sh"}
          5:
            icon: {text: "Up", emoji: "🐳", bg: "#0277bd"}
            action: {type: shell, cmd: "docker compose up -d"}
          6:
            icon: {text: "Down", emoji: "🐳", bg: "#01579b"}
            action: {type: shell, cmd: "docker compose down"}
          7:
            icon: {text: "Nginx", emoji: "🔁", bg: "#388e3c"}
            action: {type: shell, cmd: "sudo systemctl reload nginx"}
          8:
            icon: {text: "Install", emoji: "📦", bg: "#7b1fa2"}
            action: {type: shell, cmd: "{{vars.pnpm}} install"}
          9:
            icon: {text: "scripts/", emoji: "📂", bg: "#5d4037"}
            action: {type: shell, cmd: "xdg-open ~/scripts"}
          10:
            icon: {text: "ngrok", emoji: "🌐", bg: "#37474f"}
            action: {type: shell, cmd: "~/scripts/ngrok-up.sh"}
          11:
            icon: {text: "repos/", emoji: "📁", bg: "#5d4037"}
            action: {type: shell, cmd: "xdg-open ~/repos"}
          12:
            icon: {text: "notes/", emoji: "📓", bg: "#5d4037"}
            action: {type: shell, cmd: "xdg-open ~/notes"}
          13:
            icon: {text: "Config", emoji: "⚙️", bg: "#455a64"}
            action: {type: shell, cmd: "${EDITOR:-vim} ~/.config/deckctl/config.yaml"}
          14:
            icon: {text: "Back", emoji: "⬅️", bg: "#424242"}
            action: {type: page.go, page: home}
```

- [ ] **Step 2: Add to DESCRIPTIONS**

In `src/deckctl/presets/__init__.py`, extend `DESCRIPTIONS`:

```python
DESCRIPTIONS: dict[str, str] = {
    "default": "Minimal 3-key smoke layout. Use after install to verify everything works.",
    "coding": "Dev workflow: tests/build/lint, git page, snippets page, tmux page, scripts page, Claude + Codex launchers.",
}
```

- [ ] **Step 3: Run schema validation**

```bash
pytest tests/unit/test_presets.py -v
```

Expected: 6 passing (3 generic + 1 schema-validation for `default` + 1 schema-validation for `coding` + 1 loader return check).

If the schema validator complains about something in coding.yaml, fix the YAML — do NOT relax the schema. The renderer requires at least one of `text`/`emoji`/`image` in every icon (no key with empty icon allowed).

- [ ] **Step 4: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 161 tests passing.

- [ ] **Step 5: Commit**

```bash
git add src/deckctl/presets/coding.yaml src/deckctl/presets/__init__.py
git commit -m "feat(presets): coding preset with 5 pages (home/git/snippets/terminal/scripts)"
```

---

## Task 4: `streaming-twitch` preset

**Files:**
- Create: `src/deckctl/presets/streaming-twitch.yaml`
- Modify: `src/deckctl/presets/__init__.py`

- [ ] **Step 1: Write the preset — `src/deckctl/presets/streaming-twitch.yaml`**

```yaml
# deckctl streaming-twitch preset.
#
# Customize:
# - Replace <user> in the Chat URL (key 10) with your Twitch handle.
# - Replace the OBS scene names (Camera, Game, BRB, etc.) with whatever
#   you've actually named your scenes in OBS Studio.
# - Set DECKCTL_OBS_LOCAL_PASS in your environment with the password from
#   OBS > Tools > WebSocket Server Settings before running the daemon.
# - If your microphone source isn't named "Mic/Aux", edit key 9.

version: 1
default_profile: streaming-twitch

obs_hosts:
  local:
    url: obsws://127.0.0.1:4455/${DECKCTL_OBS_LOCAL_PASS}

profiles:
  streaming-twitch:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Cam", emoji: "📷", bg: "#1e88e5"}
            action: {type: obs.scene.switch, host: local, scene: "Camera"}
          1:
            icon: {text: "Game", emoji: "🎮", bg: "#7b1fa2"}
            action: {type: obs.scene.switch, host: local, scene: "Game"}
          2:
            icon: {text: "BRB", emoji: "⏸", bg: "#fb8c00"}
            action: {type: obs.scene.switch, host: local, scene: "BRB"}
          3:
            icon: {text: "Start", emoji: "👋", bg: "#43a047"}
            action: {type: obs.scene.switch, host: local, scene: "Starting Soon"}
          4:
            icon: {text: "End", emoji: "🏁", bg: "#6d4c41"}
            action: {type: obs.scene.switch, host: local, scene: "Ending Soon"}
          5:
            icon:
              text: "REC"
              emoji: "🔴"
              bg_idle: "#424242"
              bg_active: "#d32f2f"
              fg: "#ffffff"
            indicator: {bind: obs.recording.state, host: local}
            action: {type: obs.recording.toggle, host: local}
          6:
            icon:
              text: "LIVE"
              emoji: "📡"
              bg_idle: "#424242"
              bg_active: "#9146ff"
              fg: "#ffffff"
            indicator: {bind: obs.streaming.state, host: local}
            action: {type: obs.streaming.toggle, host: local}
          7:
            icon: {text: "Replay", emoji: "💾", bg: "#1565c0", fg: "#ffffff"}
            action: {type: obs.replay.save, host: local}
          8:
            icon:
              text: "V-Cam"
              emoji: "🎥"
              bg_idle: "#424242"
              bg_active: "#1976d2"
              fg: "#ffffff"
            indicator: {bind: obs.virtualcam.state, host: local}
            action: {type: obs.virtualcam.toggle, host: local}
          9:
            icon:
              text: "Mic"
              emoji: "🎤"
              bg_idle: "#388e3c"
              bg_active: "#d32f2f"
              fg: "#ffffff"
            indicator: {bind: obs.input.muted, host: local, input_name: "Mic/Aux"}
            action: {type: obs.input.mute.toggle, host: local, input_name: "Mic/Aux"}
          10:
            icon: {text: "Chat", emoji: "💬", bg: "#9146ff", fg: "#ffffff"}
            action: {type: open.url, url: "https://www.twitch.tv/popout/<user>/chat"}
          11:
            icon: {text: "Dash", emoji: "📊", bg: "#7b1fa2", fg: "#ffffff"}
            action: {type: open.url, url: "https://dashboard.twitch.tv/"}
          12:
            icon: {text: "Vol-", emoji: "🔉", bg: "#37474f"}
            action: {type: system.volume.down, step: 5}
          13:
            icon: {text: "Vol+", emoji: "🔊", bg: "#37474f"}
            action: {type: system.volume.up, step: 5}
          14:
            icon: {text: "AUTO", emoji: "🤖", bg: "#1565c0", fg: "#ffffff"}
            action:
              type: compound
              actions:
                - {type: key.text, text: "defer to your decisions, scope/plan/execute autonomously, skip the question loop"}
                - {type: key.chord, keys: "Return"}
```

- [ ] **Step 2: Register in DESCRIPTIONS**

```python
DESCRIPTIONS: dict[str, str] = {
    "default": "Minimal 3-key smoke layout. Use after install to verify everything works.",
    "coding": "Dev workflow: tests/build/lint, git page, snippets page, tmux page, scripts page, Claude + Codex launchers.",
    "streaming-twitch": "Twitch streaming: 5 scenes, record/stream/replay/v-cam toggles with live indicators, mic mute, chat + dashboard launchers.",
}
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/unit/test_presets.py -v && \
ruff check src tests && mypy src && pytest -q && \
git add src/deckctl/presets/streaming-twitch.yaml src/deckctl/presets/__init__.py && \
git commit -m "feat(presets): streaming-twitch preset (OBS scenes + live indicators + Twitch links)"
```

Expected: 7 tests passing in test_presets.py; 162 total.

---

## Task 5: `streaming-youtube` preset

**Files:**
- Create: `src/deckctl/presets/streaming-youtube.yaml`
- Modify: `src/deckctl/presets/__init__.py`

- [ ] **Step 1: Write the preset — `src/deckctl/presets/streaming-youtube.yaml`**

```yaml
# deckctl streaming-youtube preset.
#
# Customize:
# - Replace <video-id> in the Chat URL (key 10) with your active live-stream
#   video ID, OR change it to https://studio.youtube.com/livestreaming.
# - Replace OBS scene names with whatever you've actually named your scenes.
# - Set DECKCTL_OBS_LOCAL_PASS in your environment before running the daemon.
# - If your microphone source isn't named "Mic/Aux", edit key 9.

version: 1
default_profile: streaming-youtube

obs_hosts:
  local:
    url: obsws://127.0.0.1:4455/${DECKCTL_OBS_LOCAL_PASS}

profiles:
  streaming-youtube:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Cam", emoji: "📷", bg: "#1e88e5"}
            action: {type: obs.scene.switch, host: local, scene: "Camera"}
          1:
            icon: {text: "Screen", emoji: "🖥️", bg: "#7b1fa2"}
            action: {type: obs.scene.switch, host: local, scene: "Screen"}
          2:
            icon: {text: "BRB", emoji: "⏸", bg: "#fb8c00"}
            action: {type: obs.scene.switch, host: local, scene: "BRB"}
          3:
            icon: {text: "Start", emoji: "👋", bg: "#43a047"}
            action: {type: obs.scene.switch, host: local, scene: "Starting Soon"}
          4:
            icon: {text: "End", emoji: "🏁", bg: "#6d4c41"}
            action: {type: obs.scene.switch, host: local, scene: "Ending"}
          5:
            icon:
              text: "REC"
              emoji: "🔴"
              bg_idle: "#424242"
              bg_active: "#d32f2f"
              fg: "#ffffff"
            indicator: {bind: obs.recording.state, host: local}
            action: {type: obs.recording.toggle, host: local}
          6:
            icon:
              text: "LIVE"
              emoji: "📡"
              bg_idle: "#424242"
              bg_active: "#ff0000"
              fg: "#ffffff"
            indicator: {bind: obs.streaming.state, host: local}
            action: {type: obs.streaming.toggle, host: local}
          7:
            icon: {text: "Replay", emoji: "💾", bg: "#1565c0", fg: "#ffffff"}
            action: {type: obs.replay.save, host: local}
          8:
            icon:
              text: "V-Cam"
              emoji: "🎥"
              bg_idle: "#424242"
              bg_active: "#1976d2"
              fg: "#ffffff"
            indicator: {bind: obs.virtualcam.state, host: local}
            action: {type: obs.virtualcam.toggle, host: local}
          9:
            icon:
              text: "Mic"
              emoji: "🎤"
              bg_idle: "#388e3c"
              bg_active: "#d32f2f"
              fg: "#ffffff"
            indicator: {bind: obs.input.muted, host: local, input_name: "Mic/Aux"}
            action: {type: obs.input.mute.toggle, host: local, input_name: "Mic/Aux"}
          10:
            icon: {text: "Chat", emoji: "💬", bg: "#ff0000", fg: "#ffffff"}
            action: {type: open.url, url: "https://www.youtube.com/live_chat?v=<video-id>"}
          11:
            icon: {text: "Studio", emoji: "📊", bg: "#cc0000", fg: "#ffffff"}
            action: {type: open.url, url: "https://studio.youtube.com/"}
          12:
            icon: {text: "Vol-", emoji: "🔉", bg: "#37474f"}
            action: {type: system.volume.down, step: 5}
          13:
            icon: {text: "Vol+", emoji: "🔊", bg: "#37474f"}
            action: {type: system.volume.up, step: 5}
          14:
            icon: {text: "AUTO", emoji: "🤖", bg: "#1565c0", fg: "#ffffff"}
            action:
              type: compound
              actions:
                - {type: key.text, text: "defer to your decisions, scope/plan/execute autonomously, skip the question loop"}
                - {type: key.chord, keys: "Return"}
```

- [ ] **Step 2: Register in DESCRIPTIONS**

```python
DESCRIPTIONS: dict[str, str] = {
    "default": "Minimal 3-key smoke layout. Use after install to verify everything works.",
    "coding": "Dev workflow: tests/build/lint, git page, snippets page, tmux page, scripts page, Claude + Codex launchers.",
    "streaming-twitch": "Twitch streaming: 5 scenes, record/stream/replay/v-cam toggles with live indicators, mic mute, chat + dashboard launchers.",
    "streaming-youtube": "YouTube streaming: 5 scenes, record/stream/replay/v-cam toggles with live indicators, mic mute, chat + Studio launchers.",
}
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/unit/test_presets.py -v && \
ruff check src tests && mypy src && pytest -q && \
git add src/deckctl/presets/streaming-youtube.yaml src/deckctl/presets/__init__.py && \
git commit -m "feat(presets): streaming-youtube preset"
```

Expected: 8 tests in test_presets.py; 163 total.

---

## Task 6: `deckctl init` CLI verb

**Files:**
- Modify: `src/deckctl/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests — append to `tests/unit/test_cli.py`**

```python
def test_init_list_prints_available_presets():
    runner = CliRunner()
    result = runner.invoke(main, ["init", "--list"])
    assert result.exit_code == 0, result.output
    assert "default" in result.output
    assert "coding" in result.output
    assert "streaming-twitch" in result.output
    assert "streaming-youtube" in result.output


def test_init_unknown_name_errors():
    runner = CliRunner()
    result = runner.invoke(main, ["init", "nonexistent"])
    assert result.exit_code == 1
    assert "unknown preset" in result.output.lower()


def test_init_writes_default_preset_to_chosen_path(tmp_path: Path):
    out = tmp_path / "config.yaml"
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "version: 1" in out.read_text()
    assert "default_profile: default" in out.read_text()


def test_init_refuses_to_overwrite_existing_without_force(tmp_path: Path):
    out = tmp_path / "config.yaml"
    out.write_text("# existing config\n")
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out)])
    assert result.exit_code == 2
    assert "already exists" in result.output.lower()
    assert out.read_text() == "# existing config\n"  # unchanged


def test_init_force_overwrites(tmp_path: Path):
    out = tmp_path / "config.yaml"
    out.write_text("# existing\n")
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out), "--force"])
    assert result.exit_code == 0, result.output
    assert "version: 1" in out.read_text()


def test_init_no_args_shows_usage_with_preset_list():
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code != 0
    assert "coding" in result.output or "default" in result.output
```

- [ ] **Step 2: Run failing**

```bash
. .venv/bin/activate
pytest tests/unit/test_cli.py -k "init" -v
```

Expected: `UsageError("no such command: init")`.

- [ ] **Step 3: Implement in `src/deckctl/cli.py`**

Append (after the existing `doctor` command):

```python
@main.command()
@click.argument("name", required=False)
@click.option("--list", "list_only", is_flag=True, help="List available presets and exit.")
@click.option(
    "--to",
    "dest",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Destination path. Defaults to ~/.config/deckctl/config.yaml.",
)
@click.option("--force", is_flag=True, help="Overwrite destination if it exists.")
def init(name: str | None, list_only: bool, dest: str | None, force: bool) -> None:
    """Write a bundled preset YAML to a config path."""
    from deckctl.presets import get_preset, list_presets

    presets = list_presets()
    if list_only:
        for n, desc in sorted(presets.items()):
            click.echo(f"  {n:22} {desc}")
        return
    if name is None:
        click.echo("usage: deckctl init <preset-name> [--to PATH] [--force]", err=True)
        click.echo("", err=True)
        click.echo("Available presets:", err=True)
        for n, desc in sorted(presets.items()):
            click.echo(f"  {n:22} {desc}", err=True)
        sys.exit(2)
    if name not in presets:
        click.echo(f"unknown preset {name!r}; run `deckctl init --list` to see options", err=True)
        sys.exit(1)
    target = Path(dest) if dest else Path.home() / ".config" / "deckctl" / "config.yaml"
    if target.exists() and not force:
        click.echo(f"{target} already exists. Pass --force to overwrite.", err=True)
        sys.exit(2)
    target.parent.mkdir(parents=True, exist_ok=True)
    yaml_text = get_preset(name)
    target.write_text(yaml_text)
    try:
        target.chmod(0o600)
    except OSError:
        pass  # Windows + tmpfs ignore chmod; not fatal
    click.echo(f"Wrote {target}")
    click.echo("Edit it to customize, then run `deckctl daemon --config <path>`.")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_cli.py -k "init" -v
```

Expected: 6 passing.

- [ ] **Step 5: Manual smoke**

```bash
. .venv/bin/activate
deckctl init --list
deckctl init default --to /tmp/dc-smoke.yaml
deckctl validate /tmp/dc-smoke.yaml
```

Expected: list shows 4 presets; write succeeds; validate reports OK.

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 169 tests passing (163 prior + 6 new init tests).

- [ ] **Step 7: Commit**

```bash
git add src/deckctl/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): deckctl init <preset> with --list / --to / --force"
```

---

## Task 7: README + CHANGELOG + version bump

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/deckctl/__init__.py`
- Modify: `CHANGELOG.md`
- Modify: `README.md`

- [ ] **Step 1: Bump version**

In `pyproject.toml`:

```toml
version = "0.3.0"
```

In `src/deckctl/__init__.py`:

```python
__version__ = "0.3.0"
```

- [ ] **Step 2: Add v0.3.0 to CHANGELOG.md**

Insert at the top of CHANGELOG.md (after the header), BEFORE the `## [0.2.0]` section:

```markdown
## [0.3.0] - 2026-05-18

### Added

- **Preset library + `deckctl init <preset>`** — bundled YAMLs you can drop into your config with one command:
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

```

- [ ] **Step 3: Update README**

In `README.md`, find the `## Quick start` section. After the existing `## Quick start` heading, replace the fenced bash block with:

```bash
# 1. Install + a starter config in one shot
pipx install deckctl
deckctl init coding   # or `default`, `streaming-twitch`, `streaming-youtube`
deckctl init --list   # see all available presets

# 2. Validate (no device required)
deckctl validate ~/.config/deckctl/config.yaml

# 3. Preview as PNG (no device required)
deckctl preview ~/.config/deckctl/config.yaml --out preview.png

# 4. Run the daemon
deckctl daemon --config ~/.config/deckctl/config.yaml -v
```

Find the `**Status:** Phase 4 ...` paragraph and update it to:

```markdown
**Status:** Phase 6 (current, v0.3.0). Bundled preset library — `deckctl init coding` writes a working dev profile (5 pages, Claude + Codex launchers, AUTO key); `deckctl init streaming-twitch` or `streaming-youtube` for streamers. Plus everything from v0.2.0: `deckctl daemon` with full action grammar, OBS integration + live indicators, auto profile switching, systemd service install on Linux, Windows port (Task Scheduler install in Phase 4b).
```

- [ ] **Step 4: Build + verify**

```bash
. .venv/bin/activate
pip install -e ".[dev]" --quiet
deckctl --version  # → 0.3.0
deckctl init --list
ruff check src tests && mypy src && pytest -q
```

Expected: 0.3.0, list shows 4 presets, all checks clean.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/deckctl/__init__.py CHANGELOG.md README.md
git commit -m "chore: bump to v0.3.0 + Phase 6 CHANGELOG + README"
```

---

## Task 8: Build wheel + tag + GitHub release v0.3.0

**Files:** (none — `gh` operations)

- [ ] **Step 1: Build artifacts**

```bash
cd ~/repos/streamdeck-as-code
. .venv/bin/activate
rm -rf /tmp/deckctl-v030
python -m build --outdir /tmp/deckctl-v030
ls /tmp/deckctl-v030/
```

Expected: `deckctl-0.3.0-py3-none-any.whl` + `deckctl-0.3.0.tar.gz`.

- [ ] **Step 2: Push commits + tag**

```bash
git push origin main
git tag -a v0.3.0 -m "v0.3.0 — Phase 6 preset library (deckctl init)"
git push origin v0.3.0
```

- [ ] **Step 3: Extract release notes from CHANGELOG**

```bash
awk '/## \[0\.3\.0\]/{flag=1; next} /^## \[/{flag=0} flag' CHANGELOG.md > /tmp/v030-notes.md
head -20 /tmp/v030-notes.md
```

Expected: notes file with the v0.3.0 section content.

- [ ] **Step 4: Create release**

```bash
gh release create v0.3.0 \
    --repo solomonneas/deckctl \
    --title "v0.3.0 — Preset library (deckctl init)" \
    --notes-file /tmp/v030-notes.md \
    /tmp/deckctl-v030/deckctl-0.3.0-py3-none-any.whl \
    /tmp/deckctl-v030/deckctl-0.3.0.tar.gz
```

Expected: prints the release URL.

- [ ] **Step 5: Verify**

```bash
gh release view v0.3.0 --repo solomonneas/deckctl --json url,assets --jq '{url, assets: [.assets[].name]}'
```

Expected: 2 asset filenames + URL.

- [ ] **Step 6: Watch CI**

```bash
sleep 30
gh run list --repo solomonneas/deckctl --limit 1 --json conclusion,status,databaseId
```

Expected: `in_progress` or `completed/success`. If it failed, surface the log.

---

## Done criteria for Phase 6

1. `deckctl init --list` prints 4 presets with descriptions.
2. `deckctl init coding --to /tmp/c.yaml` writes a valid YAML that `deckctl validate /tmp/c.yaml` accepts.
3. Each bundled preset validates against the schema in `test_presets.py` (parameterized).
4. `deckctl --version` returns 0.3.0.
5. https://github.com/solomonneas/deckctl/releases/tag/v0.3.0 exists with wheel + sdist.
6. CI matrix green on the v0.3.0 commit.

## Out of scope (future phases per the spec)

- **Phase 6b**: more presets (writing, meeting, etc.) as the use case library grows.
- **Phase 7**: built-in icon library — `icon: {builtin: git}` resolves to bundled PNGs.
- **Phase 8**: named-macro library — `action: {type: git.commit}` expands to shell/key.chord.
- **Phase 9**: `deckctl edit` TUI.
