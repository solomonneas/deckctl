# AGENTS.md

Guidance for coding agents working in this repo (deckctl, a cross-platform
declarative Stream Deck driver in Python).

## Setup

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11+ is supported; CI runs 3.11 and 3.12 on Ubuntu and Windows.

## Quality gates

All three must pass before any commit lands. Run them from the repo root with
the venv active (or prefix with `.venv/bin/`):

```bash
ruff check src tests
mypy src        # strict mode, configured in pyproject.toml
pytest -q       # full suite, no device required
```

Platform-specific notes:

- `python-xlib` only installs on Linux, `pywin32`/`psutil` only on Windows
  (environment markers in pyproject.toml). Tests for the other platform must
  guard with a module-level `pytest.skip(..., allow_module_level=True)` BEFORE
  importing any platform-only module. See `tests/unit/test_watcher_linux.py`
  for the pattern; getting this wrong breaks collection on the other OS in CI.

## Renderer goldens

`tests/unit/test_render.py` compares rendered key images against PNG goldens
in `tests/fixtures/goldens/`. After an intentional rendering change:

```bash
DECKCTL_REGEN=1 pytest tests/unit/test_render.py
git status tests/fixtures/goldens/   # inspect the diff before committing
```

Commit regenerated goldens together with the rendering change that caused
them. Never regenerate to paper over an unexplained test failure.

## Testing without hardware

The daemon runs against an in-memory mock device:

```bash
deckctl daemon --config <config.yaml> --mock -v
```

`deckctl init default` writes a minimal smoke config; `deckctl init --list`
shows all bundled presets. `deckctl validate <config.yaml>` and
`deckctl preview <config.yaml> --out preview.png` also need no device.

## Releases

- Keep a Changelog format; add entries under `Unreleased` as you go.
- Version lives in BOTH `pyproject.toml` and `src/deckctl/__init__.py`; bump
  them together.
- Release only when explicitly asked, never per-feature. Do not push, tag, or
  publish without an explicit request.
- The package is not yet on PyPI; install docs point at the git URL until
  publishing happens.

## Writing rules

- No em dashes anywhere (code, docs, commits). Use hyphens, commas, periods,
  or rewrite.
- Conventional commit subjects. Never add `Co-Authored-By` trailers and never
  mention AI assistance in commit messages.
- Never put personal hostnames, real LAN IPs, or home-directory paths in
  tracked files. Use neutral placeholders (`windows-host`, `/home/user`) and
  RFC 5737 addresses (`192.0.2.x`) in examples. A hostname leak already forced
  one full history rewrite of this repo; do not cause another.
- `.claude/`, `.codex/`, `docs/superpowers/`, and memory-handoff artifacts are
  gitignored on purpose. Never force-add them.
