# streamdeck-as-code Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `streamdeck-as-code` v0.1.0 publicly at `github.com/solomonneas/streamdeck-as-code`. Polish package metadata, add a CHANGELOG, gitignore Claude artifacts, install a content-guard pre-push hook (per the user's standing repo-hygiene rule), create the GitHub repo, push `main`, tag and publish a v0.1.0 release.

**Architecture:** No new code. This phase is repo hygiene + publication. The content-guard hook is a bash script in `.git/hooks/pre-push` that scrubs for personal hostnames (the dev host, the Windows host, the infra host), local IPs, secret patterns, and `.claude/` paths before allowing a push.

**Tech Stack:** `gh` CLI (already installed + authed as solomonneas), git, bash.

---

## Scope

**In Phase 5:**
- pyproject metadata polish (Issues URL, classifiers, keywords).
- `CHANGELOG.md` listing Phase 1 → Phase 4 milestones.
- `.gitignore` additions: `.claude/`, `*.memory-handoff.md` patterns.
- `.git/hooks/pre-push` content-guard hook (scrubs hostnames + private IPs).
- `gh repo create solomonneas/streamdeck-as-code --public --source=. --push`.
- `gh release create v0.1.0` with auto-generated notes.

**Deferred (Phase 5b):**
- PyPI publish (needs API token; will document the command).
- ClawHub publish (sdac isn't an OpenClaw plugin; user may decide a separate `streamdeck-as-code-clawhub` shim is worthwhile or not).
- v0.2.0+ release cadence.

---

## Task 1: pyproject metadata polish

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add complete URL set under `[project.urls]`**

Replace the existing `[project.urls]` block in `pyproject.toml`:

```toml
[project.urls]
Repository = "https://github.com/solomonneas/streamdeck-as-code"
Issues = "https://github.com/solomonneas/streamdeck-as-code/issues"
Documentation = "https://github.com/solomonneas/streamdeck-as-code/tree/main/docs"
Changelog = "https://github.com/solomonneas/streamdeck-as-code/blob/main/CHANGELOG.md"
```

- [ ] **Step 2: Expand classifiers**

Replace the existing `classifiers = [...]` block with:

```toml
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Environment :: No Input/Output (Daemon)",
    "Intended Audience :: Developers",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia",
    "Topic :: Multimedia :: Sound/Audio",
    "Topic :: Multimedia :: Video :: Capture",
    "Topic :: System :: Hardware :: Hardware Drivers",
    "Topic :: Utilities",
]
```

- [ ] **Step 3: Verify the wheel still builds**

```bash
cd ~/repos/streamdeck-as-code
. .venv/bin/activate
pip install --quiet build
python -m build --wheel --outdir /tmp/sdac-build
ls /tmp/sdac-build/
```

Expected: `streamdeck_as_code-0.1.0-py3-none-any.whl`.

- [ ] **Step 4: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 155 tests passing.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: pyproject metadata polish (URLs + classifiers)"
```

---

## Task 2: CHANGELOG.md

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Write `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-17

Initial public release. Covers Phase 1 through Phase 4 of the implementation roadmap
(see `docs/superpowers/specs/2026-05-17-streamdeck-as-code-design.md`).

### Added

**Phase 1 - Foundation**
- Pydantic v2 schema for the YAML config (discriminated union over 21 action types).
- `${ENV_VAR}` substitution across the entire parsed YAML tree.
- POSIX file permission check (`--strict-perms`).
- `sdac validate <config>` CLI verb.
- Pillow + Pilmoji icon renderer (text, emoji, image-background, state variants).
- `sdac preview <config>` CLI verb - renders the full profile as a mosaic PNG.
- Bundled rsms/inter v4.0 Inter-Bold.ttf for deterministic icon rendering.
- GitHub Actions CI on Ubuntu + Windows, Python 3.11 + 3.12.

**Phase 2a - Daemon + actions**
- USB HID I/O via `python-elgato-streamdeck` for Stream Deck MK.2.
- Cross-platform `Device` protocol with `MockDevice` for tests.
- Synchronous threaded daemon, hot-reload via `watchdog`.
- Built-in action handlers: `shell`, `key.chord`, `key.text`, `open.url`, `open.app`, `system.volume.up/down/mute`, `media.play/pause/next/prev`, `page.go`, `profile.switch`, `compound`.
- Linux platform shim (xdotool / pactl / playerctl). Windows stubs.
- `sdac daemon --config <path> [--mock]` CLI verb.
- Device hotplug resilience + SIGINT/SIGTERM clean shutdown.

**Phase 2b - Service install + doctor**
- `sdac install-service` writes a systemd user unit + udev rule via sudo.
- `sdac uninstall-service` reverses; `--keep-udev` opt.
- `sdac doctor` reports device, libhidapi, python_deps, system_binaries, udev, service, config, and OBS reachability (added in Phase 3).

**Phase 3 - OBS integration**
- All 6 OBS action handlers execute via `obs-cmd` shell-out.
- `OBSClient` per host via `obsws-python` EventClient.
- Live state indicators: recording / streaming / replay / virtualcam / scene / input-mute keys re-render on OBS events.
- Daemon best-effort connects to each `obs_hosts` entry on startup; unreachable hosts log + skip.

**Phase 4 - Auto profile switching**
- Linux X11 active-window watcher via `python-xlib` polling `_NET_ACTIVE_WINDOW`.
- Windows watcher via pywin32 + psutil (untested on Linux dev; ready for runtime verification on Windows).
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
- Real-hardware smoke verified end-to-end on a Stream Deck MK.2 plugged into the dev host.

### Required runtime deps (Linux)

- `libhidapi-libusb0` - daemon fails to enumerate without it.
- `xdotool` - `key.chord` / `key.text`.
- `pactl` (pulseaudio-utils or pipewire-pulse) - `system.volume.*`.
- `playerctl` - `media.*`.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG.md for v0.1.0"
```

---

## Task 3: gitignore Claude artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append Claude-artifact patterns to `.gitignore`**

Append to the end of `.gitignore`:

```
# Claude / superpowers artifacts (per repo-hygiene rule)
.claude/
.claude.local/
**/memory-handoffs/
.cursor/
.windsurf/
```

- [ ] **Step 2: Verify no Claude artifacts are currently tracked**

```bash
cd ~/repos/streamdeck-as-code
git ls-files | grep -E '\.claude|memory-handoff' || echo "no Claude artifacts tracked"
```

Expected: `no Claude artifacts tracked`.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore Claude artifacts (.claude/, memory-handoffs/)"
```

---

## Task 4: content-guard pre-push hook

**Files:**
- Create: `.git/hooks/pre-push` (NOT tracked - installed at workdir, scoped to this clone)
- Create: `scripts/install-content-guard.sh` (tracked - lets others install the same hook)

- [ ] **Step 1: Write `scripts/install-content-guard.sh`**

```bash
#!/usr/bin/env bash
# Install a pre-push hook that scrubs for personal hostnames + private IPs +
# the .claude/ directory before allowing a push. Idempotent.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
HOOK=".git/hooks/pre-push"
cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# content-guard pre-push hook for streamdeck-as-code
# Blocks pushes that would leak personal hostnames, private LAN IPs, or
# Claude artifacts.
set -euo pipefail

remote="$1"
url="$2"

# Read the refs to be pushed from stdin (git pre-push protocol)
while read local_ref local_sha remote_ref remote_sha; do
  if [[ "$local_sha" = "0000000000000000000000000000000000000000" ]]; then
    continue  # deletion, nothing to scan
  fi
  if [[ "$remote_sha" = "0000000000000000000000000000000000000000" ]]; then
    range="$local_sha"
  else
    range="$remote_sha..$local_sha"
  fi

  patterns=(
    'the dev host'
    'the Windows host'
    'the infra host'
    '192\.168\.4\.[0-9]{1,3}'
    '\.claude/'
    '\.claude\.local/'
    'memory-handoff'
    'BEGIN OPENSSH PRIVATE KEY'
    'BEGIN RSA PRIVATE KEY'
    'sk-[A-Za-z0-9]{20,}'
    'ghp_[A-Za-z0-9]{20,}'
    'AKIA[0-9A-Z]{16}'
  )

  for pat in "${patterns[@]}"; do
    if git rev-list "$range" -- 2>/dev/null | xargs -r -I{} git show {} 2>/dev/null | grep -E "$pat" > /dev/null; then
      echo "content-guard: push BLOCKED - $pat appears in commits being pushed"
      echo "  fix: rewrite history with git filter-repo, or revert the offending commit"
      exit 1
    fi
  done
done

exit 0
EOF
chmod +x "$HOOK"
echo "installed content-guard hook at $HOOK"
```

- [ ] **Step 2: Make the script executable + run it once**

```bash
cd ~/repos/streamdeck-as-code
chmod +x scripts/install-content-guard.sh
./scripts/install-content-guard.sh
ls -la .git/hooks/pre-push
```

Expected: hook installed, executable.

- [ ] **Step 3: Verify the hook scans current commits cleanly**

```bash
# Simulate a push by running the hook directly against our current main
echo "refs/heads/main $(git rev-parse HEAD) refs/heads/main 0000000000000000000000000000000000000000" | .git/hooks/pre-push origin git@github.com:solomonneas/streamdeck-as-code.git
echo "exit: $?"
```

Expected: exit 0 (no blocked patterns found). If the hook blocks, STOP and report - there's a leak in our history we need to address before publication.

- [ ] **Step 4: Commit the install script**

```bash
git add scripts/install-content-guard.sh
git commit -m "chore: content-guard pre-push hook installer"
```

---

## Task 5: GitHub repo create + push

**Files:** (none - `gh` operations)

This task creates the public repo and pushes `main`. Single sudo-equivalent action; do it deliberately.

- [ ] **Step 1: Confirm `gh` is authed**

```bash
gh auth status 2>&1 | head -5
```

Expected: `Logged in to github.com as solomonneas`.

- [ ] **Step 2: Confirm the local repo is clean**

```bash
cd ~/repos/streamdeck-as-code
git status
git log --oneline | head -5
```

Expected: working tree clean. ~40 commits.

- [ ] **Step 3: Create the GitHub repo + push**

```bash
gh repo create solomonneas/streamdeck-as-code \
    --public \
    --source=. \
    --description="Cross-platform declarative driver for the Elgato Stream Deck. YAML config, hot reload, OBS integration, auto profile switching." \
    --push
```

Expected: success message + repo URL printed. If the repo already exists, `gh` will error - in that case run `gh repo view solomonneas/streamdeck-as-code` to confirm, then `git remote add origin git@github.com:solomonneas/streamdeck-as-code.git && git push -u origin main`.

- [ ] **Step 4: Verify the push landed**

```bash
gh repo view solomonneas/streamdeck-as-code --json defaultBranchRef,visibility,pushedAt
```

Expected: JSON showing `main` as default branch, `PUBLIC`, recent `pushedAt`.

- [ ] **Step 5: Confirm CI is running**

```bash
sleep 5
gh run list --repo solomonneas/streamdeck-as-code --limit 3
```

Expected: a `ci` workflow either `queued` / `in_progress` / `completed`. If CI shows `failure`, capture the URL and surface it in the status report - it's recoverable, not a blocker for the release.

---

## Task 6: GitHub release v0.1.0

**Files:** (none - `gh` operation)

- [ ] **Step 1: Tag and release**

```bash
cd ~/repos/streamdeck-as-code
git tag -a v0.1.0 -m "v0.1.0 - initial public release (Phases 1-4)"
git push origin v0.1.0
gh release create v0.1.0 \
    --title "v0.1.0 - Initial public release" \
    --notes-from-tag \
    --notes "$(awk '/## \[0\.1\.0\]/,/^## \[/' CHANGELOG.md | head -n -1)"
```

Expected: release URL printed.

- [ ] **Step 2: Verify the release page exists**

```bash
gh release view v0.1.0 --repo solomonneas/streamdeck-as-code | head -20
```

Expected: release metadata + body shown.

- [ ] **Step 3: Report the full Phase 5 commit chain + release URL**

```bash
git log --oneline 88f2d7e..HEAD
echo "---"
gh release view v0.1.0 --json url --jq .url
```

Save the release URL for the final session summary.

---

## Done criteria for Phase 5

1. `gh repo view solomonneas/streamdeck-as-code` returns a public repo.
2. `main` branch is pushed.
3. CI workflow is running (or has run successfully).
4. `v0.1.0` tag pushed and a GitHub release exists with the v0.1.0 CHANGELOG section as notes.
5. `.git/hooks/pre-push` content-guard hook is installed locally.
6. pyproject metadata has proper URLs + classifiers.
7. CHANGELOG.md exists and covers Phases 1-4.

## Out of scope (Phase 5b)

- PyPI publish (`twine upload`).
- ClawHub publish.
- Beyond-v0.1.0 release cadence.
- Issue templates / PR templates / `.github/` polish.

## Out of scope (Phase 4b)

- Windows `install-service` (Task Scheduler).
- Windows `volume_*` (pycaw).
