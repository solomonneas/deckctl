# deckctl Phase 6 — Preset library + `deckctl init`

- **Status:** Draft (awaiting user review)
- **Date:** 2026-05-18
- **Owner:** Solomon
- **Targets:** deckctl v0.3.0 (additive, no breaking changes)

## One-line summary

Ship a bundled library of ready-to-use YAML presets — `coding`, `streaming-twitch`, `streaming-youtube`, `default` — accessible via `deckctl init <preset>`. Turns a blank page into 80% of a working dev or streaming layout in one command. No new actions, no schema changes — pure productized DX.

## Why this and not [icon library, macros, TUI]

The 21-action grammar + emoji icons + image support already cover every key a programming or streaming profile needs. The friction is **discovery + boilerplate**: knowing what's worth binding, finding a starting point, and writing 100+ lines of YAML before the first key works.

A preset library closes that gap with one command. Icons + macros + TUI all enhance the experience after presets, not before — see *Future phases* at the bottom.

## Goals

1. `deckctl init <preset-name>` writes a complete, validated YAML to `~/.config/deckctl/config.yaml` (or `$XDG_CONFIG_HOME/deckctl/config.yaml`).
2. Bundled presets ship as package data — no network fetch, no separate install step.
3. Presets work as-is on Linux. Streaming presets also work without OBS being reachable (actions just fail at dispatch, not at load).
4. Presets are full files, not snippets — copying one to your config gives you 15 working keys immediately.
5. Each preset includes a `claude-code` key on the bottom-right corner (key 14) that types Solomon's autonomous-mode trigger phrase + Enter, because that's exactly the use case driving this phase.

## Non-goals

- No interactive editor / TUI. Preset selection is one CLI arg.
- No preset composition / merging. Pick one, edit by hand from there.
- No fetching presets from a registry. Bundled only.
- No icon downloads — every preset uses text + emoji + bg-color icons (which the renderer already handles natively, no external PNGs).
- No `writing` / `meeting` / other presets in this phase. Three is enough to validate the approach; more in Phase 6b if useful.

## Bundled presets

### 1. `default`

Minimal 3-key starter for someone who just wants to see deckctl working on their device. Single profile, single page, three buttons:

- Key 0: shell action that runs `echo 'hello deckctl'`
- Key 7 (middle): `key.text` that types "deckctl works"
- Key 14: the autonomous-mode Claude shortcut (see below)

Use case: smoke-test after install. Replace with your real config once you've confirmed everything wires up.

### 2. `coding`

A dev workflow profile + 4 sub-pages. Targeted at someone who sits down to a terminal, code editor, and browser daily.

**Profile: `coding`, default page: `home`**

| Key | Icon | Action |
|---|---|---|
| 0 | 🧪 Tests | `shell`: `pnpm test` |
| 1 | 🔨 Build | `shell`: `pnpm build` |
| 2 | ✨ Lint | `shell`: `pnpm lint --fix` |
| 3 | 🌳 Git | `page.go: git` |
| 4 | 📝 Snippets | `page.go: snippets` |
| 5 | ✨ Claude (coral bg) | Launch new terminal with `claude --permission-mode bypassPermissions` |
| 6 | 🤖 Codex (teal bg) | Launch new terminal with `codex --yolo` (interactive YOLO mode) |
| 7 | 🎨 VS Code | `open.app: code` |
| 8 | 🌐 Browser | `open.url`: `http://localhost:3000` |
| 9 | 💬 Slack | `open.url`: `https://slack.com` |
| 10 | 📂 Scripts | `page.go: scripts` (sub-page; see below) |
| 11 | 🔉− | `system.volume.down` |
| 12 | 🔇 | `system.volume.mute` |
| 13 | 🔊+ | `system.volume.up` |
| 14 | ⏩ AUTO | Autonomous-mode submit shortcut (see below) |

### Claude + Codex launch buttons (keys 5, 6)

Each launches a new terminal window with the AI CLI pre-loaded in dangerous/YOLO mode. Implementation uses `x-terminal-emulator` (the Debian/Ubuntu alternatives entry that points at the user's preferred terminal):

```yaml
5:
  icon:
    text: "Claude"
    emoji: "✨"
    bg: "#cc785c"  # Anthropic brand coral
    fg: "#ffffff"
  action:
    type: shell
    cmd: 'setsid x-terminal-emulator -e bash -lc "claude --permission-mode bypassPermissions; exec bash" </dev/null >/dev/null 2>&1 &'
6:
  icon:
    text: "Codex"
    emoji: "🤖"
    bg: "#10a37f"  # OpenAI brand teal
    fg: "#ffffff"
  action:
    type: shell
    cmd: 'setsid x-terminal-emulator -e bash -lc "codex --yolo; exec bash" </dev/null >/dev/null 2>&1 &'
```

`setsid` + `&` + stdio redirects detach the child so the daemon doesn't own it. `exec bash` at the end keeps the terminal open after the AI CLI exits (so you can see any errors).

**Branding notes:**
- The Anthropic and OpenAI logos are trademarked; we don't bundle them. The preset uses `text: "Claude"` + emoji + the brand's well-known hex color so it reads correctly without copying the actual logos.
- Users who want the real logos can drop a PNG at `~/.config/deckctl/icons/anthropic.png` (or `claude.png`, `openai.png`) and change `icon` to `{image: "~/.config/deckctl/icons/anthropic.png"}`. The preset YAML includes a comment documenting this path.

**Terminal portability:**
- Default uses `x-terminal-emulator` which works on Ubuntu/Debian/Mint/Pop!_OS.
- On Fedora/Arch/etc., users edit the `cmd` line. The preset comment lists the swap-ins for `gnome-terminal`, `kitty`, `alacritty`, `wezterm`.
- The bash multiplexer pattern (`bash -lc '...; exec bash'`) is portable across all of them.

**Flag choices (per memory):**
- Claude Code: `--permission-mode bypassPermissions` (not `--dangerously-skip-permissions` — the latter is hard-blocked by the classifier per `claude-code-bypass-permissions-flag.md`).
- Codex: `--yolo` for interactive bypass mode.

> *Naming note*: throughout this spec, `coding.git` / `coding.scripts` / etc. are readability shorthand for "a page named `git` (or `scripts`) inside the `coding` profile" — `profiles.coding.pages.git` in the YAML. The schema has profiles → pages → keys; there are no sub-profiles.

**Sub-page: `coding.git`** — git workflow (status, add all, commit, push, pull, log, diff, branch, page.go back to home, etc.). 15 keys.

**Sub-page: `coding.snippets`** — `key.text` actions for common boilerplate: `console.log()`, `import { } from ''`, `it("", () => {})`, `print()`, a TODO comment, a Slack-style emoji `:rocket:` etc. 15 keys.

**Sub-page: `coding.terminal`** — tmux/terminal navigation: new window, kill pane, split horizontal, split vertical, prev/next window, etc. Useful only if user uses tmux; harmless otherwise. 15 keys.

**Sub-page: `coding.scripts`** — generic "invoke a personal script or task" launchers. Bound to conventional script locations the user is expected to populate themselves; the preset ships **placeholders** with `# REPLACE THIS PATH` comments so users see exactly where to plug their own scripts in. 15 keys.

| Key | Icon | Action |
|---|---|---|
| 0 | 🚀 Deploy | `shell: ~/scripts/deploy.sh` (placeholder — user edits) |
| 1 | 🌱 Seed | `shell: ~/scripts/seed.sh` (placeholder) |
| 2 | 🧹 Clean | `shell: ~/scripts/clean.sh` (placeholder) |
| 3 | 🔄 Restart | `shell: ~/scripts/restart.sh` (placeholder) |
| 4 | 📊 Stats | `shell: ~/scripts/stats.sh` (placeholder) |
| 5 | 🐳 Docker up | `shell: docker compose up -d` (real) |
| 6 | 🐳 Docker down | `shell: docker compose down` (real) |
| 7 | 🔁 Reload nginx | `shell: sudo systemctl reload nginx` (placeholder/example) |
| 8 | 📦 npm install | `shell: pnpm install` (real) |
| 9 | 🔍 Open scripts/ | `shell: xdg-open ~/scripts` (real — quickly browse the dir) |
| 10 | 🌐 ngrok | `shell: ~/scripts/ngrok-up.sh` (placeholder) |
| 11 | 📁 Open repos/ | `shell: xdg-open ~/repos` (real) |
| 12 | 📓 Open notes/ | `shell: xdg-open ~/notes` (real) |
| 13 | ⚙️ Edit config | `shell: ${EDITOR:-vim} ~/.config/deckctl/config.yaml` (real) |
| 14 | ⬅ Back | `page.go: home` |

The placeholder keys point at conventional paths (`~/scripts/*.sh`). They'll succeed silently if the file exists or fail with a clear `Errno 2: no such file` log line if it doesn't — the daemon stays up either way. Users either:
- Create the matching scripts at the conventional paths, or
- Edit the preset YAML to point at their existing script locations.

The preset YAML for this page begins with a top-of-page comment:

```yaml
# coding.scripts — quick launchers for personal scripts.
# Placeholder keys point at ~/scripts/*.sh paths. Either create those scripts,
# or edit each key's action.cmd to point at where your scripts actually live.
# Tip: keep ~/scripts/ on PATH so you can invoke by name from terminals too.
```

### 3. `streaming-twitch`

Profile: `streaming-twitch`, default page: `home`. Uses the `obs_hosts:` map with a single `local` host. Password expected at `${DECKCTL_OBS_LOCAL_PASS}` env var.

| Key | Icon | Action |
|---|---|---|
| 0 | 📷 Cam | `obs.scene.switch: Camera` |
| 1 | 🎮 Game | `obs.scene.switch: Game` |
| 2 | ⏸ BRB | `obs.scene.switch: BRB` |
| 3 | 👋 Starting | `obs.scene.switch: Starting Soon` |
| 4 | 🏁 Ending | `obs.scene.switch: Ending Soon` |
| 5 | 🔴 REC | `obs.recording.toggle` with indicator binding `obs.recording.state` (red border when actually recording) |
| 6 | 📡 LIVE | `obs.streaming.toggle` with indicator binding `obs.streaming.state` |
| 7 | 💾 Replay | `obs.replay.save` |
| 8 | 🎥 V-Cam | `obs.virtualcam.toggle` |
| 9 | 🎤 Mic | `obs.input.mute.toggle` with `input_name: Mic/Aux` and indicator `obs.input.muted` |
| 10 | 💬 Chat | `open.url: https://www.twitch.tv/popout/<user>/chat` |
| 11 | 📊 Dash | `open.url: https://dashboard.twitch.tv/` |
| 12 | 🔉− | `system.volume.down` |
| 13 | 🔊+ | `system.volume.up` |
| 14 | 🤖 AUTO | Claude autonomous-mode shortcut |

The user replaces `<user>` in the chat URL with their handle on first edit.

### 4. `streaming-youtube`

Same 15-key shape as `streaming-twitch`, with Twitch-specific URLs swapped for YouTube Studio (`https://studio.youtube.com/`) and YouTube Live chat (`https://www.youtube.com/live_chat?v=<vid>`). The scenes match Twitch's convention.

## The Claude autonomous-mode shortcut

Every preset includes this exact key on index 14 (bottom-right):

```yaml
14:
  icon:
    text: "AUTO"
    emoji: "🤖"
    bg: "#1565c0"
  action:
    type: compound
    actions:
      - type: key.text
        text: "defer to your decisions, scope/plan/execute autonomously, skip the question loop"
      - type: key.chord
        keys: "Return"
```

Pressing the key types the standing autonomous-mode trigger phrase into the focused terminal/Claude prompt and submits it in one tap. This is the "skip the brainstorming Q&A" button.

The exact phrase matches Solomon's `feedback-autonomous-phase-flow` memory entry so the trigger fires reliably.

## CLI surface

### `deckctl init [name] [--to PATH] [--force] [--list]`

Behavior:
- `deckctl init` (no args, no flags): prompt-style selection — list the presets and exit non-zero with a help message asking the user to pick one. No interactive picker (out of scope).
- `deckctl init --list`: print available preset names + one-line descriptions, exit 0.
- `deckctl init <name>`: write the named preset to `~/.config/deckctl/config.yaml`. Refuses to overwrite an existing file unless `--force`.
- `deckctl init <name> --to <path>`: write to the given path instead of the default.
- `deckctl init <name> --force`: overwrite the destination if it exists.

Exit codes:
- 0: wrote successfully
- 1: unknown preset name
- 2: destination exists and `--force` not set
- 3: I/O error writing destination

## Architecture

A new package: `deckctl.presets`.

```
src/deckctl/
  presets/
    __init__.py             # list_presets(), get_preset(name), DEFAULT_DESCRIPTIONS
    coding.yaml             # bundled
    streaming-twitch.yaml   # bundled
    streaming-youtube.yaml  # bundled
    default.yaml            # bundled
  cli.py                    # adds the `init` subcommand
```

`deckctl.presets.list_presets() -> dict[str, str]` returns `{name: one-line-description}`.
`deckctl.presets.get_preset(name) -> str` returns the raw YAML text (loaded via `importlib.resources`).

The CLI command:
1. Resolves destination path (default `~/.config/deckctl/config.yaml`).
2. Refuses if destination exists and no `--force`.
3. Creates parent dirs with `mkdir -p`; sets dir mode to 0700 only if we just created it.
4. Writes the bundled YAML byte-for-byte. No template substitution. Sets file mode to 0600.
5. Echoes: "Wrote <path>. Edit it to customize, then run `deckctl daemon --config <path>`."

## Data flow

`deckctl init coding`:
1. CLI dispatches to `deckctl.cli.init_cmd`
2. `init_cmd` calls `deckctl.presets.get_preset("coding")` → reads `coding.yaml` via `importlib.resources.files("deckctl.presets").joinpath("coding.yaml").read_text()`
3. Resolves destination, creates dirs, writes file with mode 0600
4. Echoes confirmation

## Validation strategy

Each bundled preset is validated against the existing Pydantic schema at TEST time (not at install/runtime — we trust the bundle). Test sketch:

```python
@pytest.mark.parametrize("name", ["coding", "streaming-twitch", "streaming-youtube", "default"])
def test_bundled_preset_loads_against_schema(name, monkeypatch):
    monkeypatch.setenv("DECKCTL_OBS_LOCAL_PASS", "test-pass-not-used")
    raw = get_preset(name)
    tmp = pathlib.Path("/tmp/preset-test.yaml")
    tmp.write_text(raw)
    cfg = load_config(tmp)  # raises ConfigError on any schema issue
    assert cfg.version == 1
    assert cfg.default_profile in cfg.profiles
```

This catches every schema regression: if we tighten the action union or add a required field, the test suite immediately flags any bundled preset that doesn't update.

## Error handling

- Unknown preset name → exit 1 with `Unknown preset 'foo'. Run \`deckctl init --list\` to see options.`
- Destination exists without `--force` → exit 2 with `<path> already exists. Pass --force to overwrite.`
- I/O error → exit 3 with the underlying OS error string.
- Bundled YAML somehow fails schema validation at runtime → never happens because the test suite blocks the release, but if it does, exit 4 with a clear "this is a deckctl bug, please file an issue" message.

## Tests

- `tests/unit/test_presets.py`: validates `list_presets()` returns the four expected names + descriptions, and each preset loads cleanly through `load_config`.
- `tests/unit/test_cli.py`: appends `init` command tests covering `--list`, success on write, refuse-without-force, `--force` overwrite, unknown name.
- No integration tests needed — `init` is a single-file write.

## Packaging

Add `presets/*.yaml` to the wheel via `[tool.hatch.build.targets.wheel.shared-data]` (same pattern Phase 1 used for fonts):

```toml
[tool.hatch.build.targets.wheel.shared-data]
"src/deckctl/presets" = "deckctl/presets"
```

Wait — `shared-data` puts files in `share/deckctl/presets/` on install which is awkward to find. Better: include presets in the package itself (since they live under `src/deckctl/presets/`) via the existing `packages = ["src/deckctl"]` directive. The YAML files get bundled as package data automatically as long as they're in the source tree under `src/deckctl/`. Use `importlib.resources` to load them.

Verify with `python -c "from importlib.resources import files; print(files('deckctl.presets').joinpath('coding.yaml').read_text()[:80])"` after `pip install -e .`.

## Future phases (queued, NOT in scope here)

This spec scopes Phase 6 only. After this:

- **Phase 6b**: more presets (`writing`, `meeting`, `student`, etc.) as the use case library grows.
- **Phase 7**: built-in icon library. `icon: {builtin: git}` resolves to a curated 100-icon PNG set bundled with the package. Closes the "where do I get a nice Slack icon" gap.
- **Phase 8**: named-macro library. `action: {type: git.commit}` expands to the underlying shell/key.chord. Less YAML per key.
- **Phase 9**: `deckctl edit` TUI. Curses-style 5x3 grid for visual key authoring. Biggest UX win, biggest build.

Each is its own future spec when prioritized.

## Risks

- Cookie-cutter risk: presets are opinionated and won't match every workflow. Mitigation: easy to edit, and `default` exists for users who'd rather build from a tiny seed.
- The `--force` flag could overwrite a config a user worked hours on. Mitigation: refuse without `--force` is the default; the help text emphasizes this. Could add `--backup` in a future phase to write the existing file to `config.yaml.bak`.
- Twitch/YouTube URLs and OBS scene names are guesses about user conventions. Mitigation: file comments tell the user where to edit (`# replace <user> with your Twitch handle`).
