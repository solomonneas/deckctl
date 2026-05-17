# streamdeck-as-code Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a pipx-installable `streamdeck-as-code` package with three working CLI verbs (`sdac --version`, `sdac validate`, `sdac preview`) that round-trip a YAML config through Pydantic schemas and render every key as a 72×72 image, no USB device required. This is the foundation every later phase builds on.

**Architecture:** Python 3.11+ src-layout package. Pydantic v2 schemas with a discriminated union for actions. PyYAML loader with `${ENV_VAR}` substitution. Pillow renderer producing 72×72 RGB JPEGs, color emoji via Pilmoji. Click CLI. pytest + ruff + mypy in CI on Ubuntu and Windows. No daemon, no USB, no OBS execution in this phase — only schema validation and icon rendering.

**Tech Stack:** Python 3.11+, hatchling, Click 8, Pydantic v2, PyYAML 6, Pillow 10+, Pilmoji 2, pytest 8, pytest-cov, ruff, mypy, GitHub Actions.

---

## File Structure

```
streamdeck-as-code/
  pyproject.toml                       # Build config + deps + entrypoint
  README.md                            # Install + Phase 1 quickstart
  LICENSE                              # MIT
  .gitignore                           # Python defaults
  .python-version                      # 3.11
  .github/workflows/ci.yml             # lint + tests on Ubuntu + Windows
  src/sdac/
    __init__.py                        # __version__
    __main__.py                        # python -m sdac → cli.main()
    cli.py                             # Click commands: validate, preview, version
    config.py                          # Pydantic models, YAML loader, env substitution, perms check
    render.py                          # Pillow renderer; KeyImage and mosaic output
    errors.py                          # Custom exceptions
    assets/
      fonts/
        Inter-Bold.ttf                 # Bundled font for icon text
  tests/
    __init__.py
    unit/
      __init__.py
      test_config.py                   # Schema, env vars, perms, loader
      test_render.py                   # Icon rendering, mosaic, state variants
      test_cli.py                      # CLI command surface via CliRunner
    fixtures/
      __init__.py
      configs/
        minimal.yaml
        comprehensive.yaml
        invalid_schema.yaml
        env_var.yaml
      images/
        test-icon.png                  # 256×256 RGBA for image background tests
      goldens/                         # PNG goldens for renderer (regenerate via SDAC_REGEN=1)
        text_only_blue.png
        text_emoji_blue.png
        image_background.png
        state_active.png
        state_pressed.png
        state_error.png
        state_disconnected.png
  docs/
    superpowers/
      specs/2026-05-17-streamdeck-as-code-design.md   # exists
      plans/2026-05-17-streamdeck-as-code-phase1.md   # this file
    schema.md                          # Public YAML schema reference (built in Task 15)
```

**Boundary rules each task respects:**
- `config.py` knows nothing about Pillow.
- `render.py` knows nothing about YAML or Pydantic. Takes a typed `KeyView` value object.
- `cli.py` is the only module that imports both.
- `errors.py` owns all exception classes; every module raises only from this set.

---

## Task 1: Repo scaffolding, pyproject, deps, baseline tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.python-version`
- Create: `LICENSE`
- Create: `README.md`
- Create: `src/sdac/__init__.py`
- Create: `src/sdac/__main__.py`
- Create: `src/sdac/errors.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/fixtures/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "streamdeck-as-code"
version = "0.1.0"
description = "Cross-platform declarative Stream Deck driver: YAML config, hot reload, OBS integration."
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "Solomon", email = "srneas@gmail.com" }]
requires-python = ">=3.11"
keywords = ["streamdeck", "elgato", "obs", "automation", "macros"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
    "Topic :: Multimedia",
]
dependencies = [
    "click>=8.1",
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "pillow>=10.2",
    "pilmoji>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "ruff>=0.4",
    "mypy>=1.10",
    "types-PyYAML",
]

[project.scripts]
sdac = "sdac.cli:main"

[project.urls]
Repository = "https://github.com/solomonneas/streamdeck-as-code"

[tool.hatch.build.targets.wheel]
packages = ["src/sdac"]

[tool.hatch.build.targets.wheel.shared-data]
"src/sdac/assets" = "sdac/assets"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-ra --strict-markers"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
files = ["src/sdac"]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
dist/
build/
*.so
htmlcov/
.coverage
preview*.png
!tests/fixtures/goldens/*.png
```

- [ ] **Step 3: Write `.python-version`**

```
3.11
```

- [ ] **Step 4: Write `LICENSE`** (MIT)

```
MIT License

Copyright (c) 2026 Solomon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 5: Write minimal `README.md` placeholder** (full README in Task 15)

```markdown
# streamdeck-as-code

Cross-platform declarative Stream Deck driver. YAML config compiles to a live daemon (later phases); this Phase 1 build supports schema validation and offline icon preview.

See [docs/superpowers/specs/2026-05-17-streamdeck-as-code-design.md](docs/superpowers/specs/2026-05-17-streamdeck-as-code-design.md) for the full design.

## Status

Phase 1 (current): config schema + preview. No USB device required.

## Quick start (Phase 1)

```bash
pipx install streamdeck-as-code
sdac --version
sdac validate path/to/config.yaml
sdac preview path/to/config.yaml --out preview.png
```
```

- [ ] **Step 6: Write `src/sdac/__init__.py`**

```python
"""streamdeck-as-code — cross-platform declarative Stream Deck driver."""

__version__ = "0.1.0"
```

- [ ] **Step 7: Write `src/sdac/__main__.py`**

```python
"""Allow `python -m sdac`."""

from sdac.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Write `src/sdac/errors.py`** (exception hierarchy used by later tasks)

```python
"""Exception hierarchy for streamdeck-as-code.

All custom exceptions inherit from SdacError so callers can catch the
package's errors without catching unrelated exceptions.
"""


class SdacError(Exception):
    """Base class for all streamdeck-as-code errors."""


class ConfigError(SdacError):
    """Raised when a config file cannot be loaded or validated."""


class ConfigPermissionError(ConfigError):
    """Raised when the config file's POSIX permissions are too open."""


class EnvVarMissingError(ConfigError):
    """Raised when a `${VAR}` substitution refers to an unset env var."""


class RenderError(SdacError):
    """Raised when an icon cannot be rendered (asset missing, bad spec, etc.)."""
```

- [ ] **Step 9: Write empty `__init__.py` files** for the test packages

```python
# tests/__init__.py
```

```python
# tests/unit/__init__.py
```

```python
# tests/fixtures/__init__.py
```

- [ ] **Step 10: Create venv + install in editable mode + verify**

Run:
```bash
cd ~/repos/streamdeck-as-code
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -c "import sdac; print(sdac.__version__)"
ruff check src tests
mypy src
pytest -q
```

Expected: `0.1.0`, ruff clean, mypy clean (no source modules with code yet), `pytest` returns "no tests ran" with exit 5.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml .gitignore .python-version LICENSE README.md \
        src/sdac/__init__.py src/sdac/__main__.py src/sdac/errors.py \
        tests/__init__.py tests/unit/__init__.py tests/fixtures/__init__.py
git commit -m "feat: scaffold package, deps, exception hierarchy"
```

---

## Task 2: CLI skeleton with --version

**Files:**
- Create: `src/sdac/cli.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cli.py
from click.testing import CliRunner

from sdac import __version__
from sdac.cli import main


def test_cli_version_prints_package_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0, result.output
    assert __version__ in result.output


def test_cli_help_lists_validate_and_preview():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.output
    assert "preview" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_cli.py -v`
Expected: ImportError on `sdac.cli` (module not created yet).

- [ ] **Step 3: Implement `src/sdac/cli.py`**

```python
"""Click CLI entry point. Subcommands are wired here; logic lives in
sibling modules (config, render).
"""

from __future__ import annotations

import click

from sdac import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="sdac")
def main() -> None:
    """streamdeck-as-code — declarative Stream Deck driver."""


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
def validate(config_path: str) -> None:  # noqa: D401
    """Validate a config file. Implemented in Task 8."""
    raise click.UsageError("not implemented yet (Task 8)")


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--out", type=click.Path(dir_okay=False, writable=True), default="preview.png")
@click.option("--profile", default=None, help="Profile name to preview. Defaults to default_profile.")
@click.option("--page", default=None, help="Page name to preview. Defaults to the profile's default_page.")
def preview(config_path: str, out: str, profile: str | None, page: str | None) -> None:  # noqa: D401
    """Render a profile/page as a mosaic PNG. Implemented in Task 13."""
    raise click.UsageError("not implemented yet (Task 13)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_cli.py -v`
Expected: 2 passing.

- [ ] **Step 5: Smoke `sdac` on PATH**

Run: `sdac --version`
Expected: `sdac, version 0.1.0`

- [ ] **Step 6: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): scaffold sdac group with validate + preview placeholders"
```

---

## Task 3: Config — minimal top-level schema (version, vars, default_profile)

**Files:**
- Create: `src/sdac/config.py`
- Modify: `tests/unit/test_config.py` (new)
- Create: `tests/fixtures/configs/minimal.yaml`

- [ ] **Step 1: Write `tests/fixtures/configs/minimal.yaml`**

```yaml
version: 1
default_profile: coding
profiles:
  coding:
    default_page: home
    pages:
      home:
        keys: {}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_config.py
from pathlib import Path

import pytest

from sdac.config import Config, load_config
from sdac.errors import ConfigError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_minimal_config_parses():
    cfg = load_config(FIXTURES / "minimal.yaml")
    assert isinstance(cfg, Config)
    assert cfg.version == 1
    assert cfg.default_profile == "coding"
    assert "coding" in cfg.profiles
    assert cfg.profiles["coding"].default_page == "home"
    assert cfg.profiles["coding"].pages["home"].keys == {}


def test_wrong_version_rejected(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 99\ndefault_profile: x\nprofiles: {}\n")
    with pytest.raises(ConfigError, match="version"):
        load_config(bad)


def test_default_profile_must_exist(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\ndefault_profile: ghost\nprofiles:\n  coding:\n    default_page: home\n    pages:\n      home:\n        keys: {}\n")
    with pytest.raises(ConfigError, match="default_profile"):
        load_config(bad)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_config.py -v`
Expected: ImportError on `sdac.config`.

- [ ] **Step 4: Implement minimal `src/sdac/config.py`**

```python
"""Config schema (Pydantic v2) and YAML loader.

This module is the single place YAML is parsed and validated. The rest of the
package consumes typed Pydantic models. Action and key schemas land in later
tasks; this task introduces only the top-level shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sdac.errors import ConfigError


class PageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keys: dict[int, Any] = Field(default_factory=dict)


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_page: str
    pages: dict[str, PageConfig]

    @model_validator(mode="after")
    def _default_page_exists(self) -> "ProfileConfig":
        if self.default_page not in self.pages:
            raise ValueError(f"default_page '{self.default_page}' not in pages {list(self.pages)}")
        return self


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(..., description="Schema version; only 1 is supported.")
    vars: dict[str, str] = Field(default_factory=dict)
    default_profile: str
    profiles: dict[str, ProfileConfig]

    @model_validator(mode="after")
    def _validate_top_level(self) -> "Config":
        if self.version != 1:
            raise ValueError(f"unsupported schema version: {self.version} (only 1 is supported)")
        if self.default_profile not in self.profiles:
            raise ValueError(
                f"default_profile '{self.default_profile}' not in profiles {list(self.profiles)}"
            )
        return self


def load_config(path: str | Path) -> Config:
    """Parse and validate a YAML config file. Raises ConfigError on any failure."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: top-level YAML must be a mapping")
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"{p}: schema validation failed:\n{e}") from e
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: 3 passing.

- [ ] **Step 6: Run all checks**

Run: `ruff check src tests && mypy src && pytest -q`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/config.py tests/unit/test_config.py tests/fixtures/configs/minimal.yaml
git commit -m "feat(config): minimal top-level Pydantic schema + YAML loader"
```

---

## Task 4: Config — KeyConfig + IconSpec + Action discriminated union

**Files:**
- Modify: `src/sdac/config.py`
- Modify: `tests/unit/test_config.py`
- Create: `tests/fixtures/configs/comprehensive.yaml`

- [ ] **Step 1: Write `tests/fixtures/configs/comprehensive.yaml`**

```yaml
version: 1
default_profile: coding
vars:
  pnpm: /usr/bin/pnpm
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
            action: {type: key.chord, keys: "ctrl+shift+b"}
          2:
            icon: {text: "Snippet"}
            action: {type: key.text, text: "console.log()"}
          3:
            icon: {text: "Docs", emoji: "📚", bg: "#6d4c41"}
            action: {type: open.url, url: "https://example.com"}
          4:
            icon: {text: "App"}
            action: {type: open.app, path: "/usr/bin/code"}
          5:
            icon: {text: "Git"}
            action: {type: page.go, page: git}
          6:
            icon: {text: "Stream"}
            action: {type: profile.switch, profile: streaming}
          7:
            icon: {text: "Combo"}
            action:
              type: compound
              actions:
                - {type: shell, cmd: "echo hi"}
                - {type: key.text, text: "done"}
      git:
        keys:
          0:
            icon: {text: "Back"}
            action: {type: page.go, page: home}
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
          2:
            icon: {text: "Volume"}
            action: {type: system.volume.up, step: 5}
          3:
            icon: {text: "Mute"}
            action: {type: system.volume.mute}
          4:
            icon: {text: "Next"}
            action: {type: media.next}
```

- [ ] **Step 2: Add failing tests**

```python
# Append to tests/unit/test_config.py

def test_comprehensive_config_parses_all_action_types():
    cfg = load_config(FIXTURES / "comprehensive.yaml")
    home = cfg.profiles["coding"].pages["home"].keys
    assert home[0].action.type == "shell"
    assert home[0].action.cmd == "{{vars.pnpm}} test"
    assert home[1].action.type == "key.chord"
    assert home[1].action.keys == "ctrl+shift+b"
    assert home[2].action.type == "key.text"
    assert home[2].action.text == "console.log()"
    assert home[3].action.type == "open.url"
    assert home[4].action.type == "open.app"
    assert home[5].action.type == "page.go"
    assert home[5].action.page == "git"
    assert home[6].action.type == "profile.switch"
    assert home[7].action.type == "compound"
    assert len(home[7].action.actions) == 2


def test_key_index_must_be_in_range(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
        "pages:\n      p:\n        keys:\n          99:\n            icon: {text: hi}\n"
        "            action: {type: shell, cmd: ls}\n"
    )
    with pytest.raises(ConfigError, match="key index"):
        load_config(bad)


def test_icon_state_variant_colors_optional():
    cfg = load_config(FIXTURES / "comprehensive.yaml")
    rec_key = cfg.profiles["streaming"].pages["home"].keys[1]
    assert rec_key.icon.bg_idle == "#424242"
    assert rec_key.icon.bg_active == "#d32f2f"
    assert rec_key.indicator is not None
    assert rec_key.indicator.bind == "obs.recording.state"
    assert rec_key.indicator.host == "roc"
```

- [ ] **Step 3: Run tests to verify failures**

Run: `pytest tests/unit/test_config.py -v`
Expected: AttributeError / ValidationError on the new tests.

- [ ] **Step 4: Extend `src/sdac/config.py`** — add `IconSpec`, `Indicator`, action union, `KeyConfig`, and integrate

Replace the body of `src/sdac/config.py` with this complete file:

```python
"""Config schema (Pydantic v2) and YAML loader.

Single place YAML is parsed and validated. Discriminated union over the
`type` field powers the action grammar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sdac.errors import ConfigError

MK2_KEY_COUNT = 15  # 5×3


# ---------- Icons ----------


class IconSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = None
    emoji: str | None = None
    image: str | None = None  # path relative to config file
    bg: str | None = None  # hex color, idle (default)
    bg_idle: str | None = None  # alias for bg, takes precedence when set
    bg_active: str | None = None
    bg_pressed: str | None = None
    bg_error: str | None = None
    bg_disconnected: str | None = None
    fg: str | None = "#ffffff"

    @model_validator(mode="after")
    def _must_have_visible_content(self) -> "IconSpec":
        if not any([self.text, self.emoji, self.image]):
            raise ValueError("icon must have at least one of: text, emoji, image")
        return self


class Indicator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bind: Literal[
        "obs.recording.state",
        "obs.streaming.state",
        "obs.replay.state",
        "obs.virtualcam.state",
        "obs.scene.current",
        "obs.input.muted",
    ]
    host: str
    scene: str | None = None  # used with obs.scene.current
    input_name: str | None = None  # used with obs.input.muted


# ---------- Actions (discriminated union on `type`) ----------


class _ActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShellAction(_ActionBase):
    type: Literal["shell"]
    cmd: str
    cwd: str | None = None
    shell: str | None = None


class KeyChordAction(_ActionBase):
    type: Literal["key.chord"]
    keys: str


class KeyTextAction(_ActionBase):
    type: Literal["key.text"]
    text: str


class OpenUrlAction(_ActionBase):
    type: Literal["open.url"]
    url: str


class OpenAppAction(_ActionBase):
    type: Literal["open.app"]
    path: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "OpenAppAction":
        if not (bool(self.path) ^ bool(self.name)):
            raise ValueError("open.app requires exactly one of path or name")
        return self


class ObsSceneSwitchAction(_ActionBase):
    type: Literal["obs.scene.switch"]
    host: str
    scene: str


class ObsRecordingToggleAction(_ActionBase):
    type: Literal["obs.recording.toggle"]
    host: str


class ObsStreamingToggleAction(_ActionBase):
    type: Literal["obs.streaming.toggle"]
    host: str


class ObsReplaySaveAction(_ActionBase):
    type: Literal["obs.replay.save"]
    host: str


class ObsVirtualCamToggleAction(_ActionBase):
    type: Literal["obs.virtualcam.toggle"]
    host: str


class ObsInputMuteToggleAction(_ActionBase):
    type: Literal["obs.input.mute.toggle"]
    host: str
    input_name: str


class SystemVolumeUpAction(_ActionBase):
    type: Literal["system.volume.up"]
    step: int = 5


class SystemVolumeDownAction(_ActionBase):
    type: Literal["system.volume.down"]
    step: int = 5


class SystemVolumeMuteAction(_ActionBase):
    type: Literal["system.volume.mute"]


class MediaPlayAction(_ActionBase):
    type: Literal["media.play"]


class MediaPauseAction(_ActionBase):
    type: Literal["media.pause"]


class MediaNextAction(_ActionBase):
    type: Literal["media.next"]


class MediaPrevAction(_ActionBase):
    type: Literal["media.prev"]


class PageGoAction(_ActionBase):
    type: Literal["page.go"]
    page: str


class ProfileSwitchAction(_ActionBase):
    type: Literal["profile.switch"]
    profile: str


class CompoundAction(_ActionBase):
    type: Literal["compound"]
    actions: list["Action"]
    continue_on_error: bool = False


Action = Annotated[
    Union[
        ShellAction,
        KeyChordAction,
        KeyTextAction,
        OpenUrlAction,
        OpenAppAction,
        ObsSceneSwitchAction,
        ObsRecordingToggleAction,
        ObsStreamingToggleAction,
        ObsReplaySaveAction,
        ObsVirtualCamToggleAction,
        ObsInputMuteToggleAction,
        SystemVolumeUpAction,
        SystemVolumeDownAction,
        SystemVolumeMuteAction,
        MediaPlayAction,
        MediaPauseAction,
        MediaNextAction,
        MediaPrevAction,
        PageGoAction,
        ProfileSwitchAction,
        CompoundAction,
    ],
    Field(discriminator="type"),
]

# Forward-ref fix for CompoundAction.actions
CompoundAction.model_rebuild()


# ---------- Keys / Pages / Profiles ----------


class KeyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    icon: IconSpec
    action: Action
    indicator: Indicator | None = None


class PageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keys: dict[int, KeyConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _key_indices_in_range(self) -> "PageConfig":
        for k in self.keys:
            if not 0 <= k < MK2_KEY_COUNT:
                raise ValueError(
                    f"key index {k} out of range; Stream Deck MK.2 supports 0..{MK2_KEY_COUNT - 1}"
                )
        return self


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_page: str
    pages: dict[str, PageConfig]

    @model_validator(mode="after")
    def _default_page_exists(self) -> "ProfileConfig":
        if self.default_page not in self.pages:
            raise ValueError(f"default_page '{self.default_page}' not in pages {list(self.pages)}")
        return self


# ---------- Top-level ----------


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    vars: dict[str, str] = Field(default_factory=dict)
    obs_hosts: dict[str, "ObsHost"] = Field(default_factory=dict)
    profile_rules: list["ProfileRule"] = Field(default_factory=list)
    default_profile: str
    profiles: dict[str, ProfileConfig]

    @model_validator(mode="after")
    def _validate_top_level(self) -> "Config":
        if self.version != 1:
            raise ValueError(f"unsupported schema version: {self.version} (only 1 is supported)")
        if self.default_profile not in self.profiles:
            raise ValueError(
                f"default_profile '{self.default_profile}' not in profiles {list(self.profiles)}"
            )
        # page.go targets must exist
        for pname, profile in self.profiles.items():
            for page_name, page in profile.pages.items():
                for kidx, k in page.keys.items():
                    if isinstance(k.action, PageGoAction) and k.action.page not in profile.pages:
                        raise ValueError(
                            f"profile {pname!r}, page {page_name!r}, key {kidx}: "
                            f"page.go target '{k.action.page}' not found in profile"
                        )
                    if (
                        isinstance(k.action, ProfileSwitchAction)
                        and k.action.profile not in self.profiles
                    ):
                        raise ValueError(
                            f"profile {pname!r}, page {page_name!r}, key {kidx}: "
                            f"profile.switch target '{k.action.profile}' not found"
                        )
        return self


class ObsHost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str  # obsws://host:port/password (password may be ${ENV_VAR})


class ProfileRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str
    when: "ProfileRuleWhen"


class ProfileRuleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_class: list[str] = Field(default_factory=list)  # Linux WM_CLASS
    app_name: list[str] = Field(default_factory=list)  # Windows process name


Config.model_rebuild()
ProfileRule.model_rebuild()


# ---------- Loader ----------


def load_config(path: str | Path) -> Config:
    """Parse and validate a YAML config file. Raises ConfigError on any failure."""
    p = Path(path)
    try:
        raw: Any = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: top-level YAML must be a mapping")
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"{p}: schema validation failed:\n{e}") from e
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: 6 passing (3 from Task 3 + 3 from Task 4).

- [ ] **Step 6: ruff + mypy clean**

Run: `ruff check src tests && mypy src`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/config.py tests/unit/test_config.py tests/fixtures/configs/comprehensive.yaml
git commit -m "feat(config): full schema with discriminated action union + cross-ref validation"
```

---

## Task 5: Config — `${ENV_VAR}` substitution

**Files:**
- Modify: `src/sdac/config.py`
- Modify: `tests/unit/test_config.py`
- Create: `tests/fixtures/configs/env_var.yaml`

- [ ] **Step 1: Write `tests/fixtures/configs/env_var.yaml`**

```yaml
version: 1
default_profile: streaming
obs_hosts:
  roc:
    url: obsws://127.0.0.1:4455/${SDAC_TEST_OBS_PASS}
profiles:
  streaming:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Cam"}
            action: {type: obs.scene.switch, host: roc, scene: "Camera"}
```

- [ ] **Step 2: Write failing tests**

```python
# Append to tests/unit/test_config.py
import os


def test_env_var_substitution(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "secret-from-env")
    cfg = load_config(FIXTURES / "env_var.yaml")
    assert cfg.obs_hosts["roc"].url == "obsws://127.0.0.1:4455/secret-from-env"


def test_env_var_missing_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SDAC_TEST_OBS_PASS", raising=False)
    with pytest.raises(ConfigError, match="SDAC_TEST_OBS_PASS"):
        load_config(FIXTURES / "env_var.yaml")


def test_env_var_substitution_in_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDAC_TEST_CMD", "echo hello")
    p = tmp_path / "c.yaml"
    p.write_text(
        "version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
        "pages:\n      p:\n        keys:\n          0:\n            icon: {text: hi}\n"
        "            action: {type: shell, cmd: \"${SDAC_TEST_CMD}\"}\n"
    )
    cfg = load_config(p)
    assert cfg.profiles["x"].pages["p"].keys[0].action.cmd == "echo hello"
```

- [ ] **Step 3: Run failing tests**

Run: `pytest tests/unit/test_config.py -v -k env_var`
Expected: 3 failing.

- [ ] **Step 4: Add substitution logic** to `src/sdac/config.py`

Add this helper near the top of the module (after imports, before classes):

```python
import os
import re

from sdac.errors import EnvVarMissingError

_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _substitute_env(raw: Any) -> Any:
    """Recursively substitute `${VAR}` in every string in the parsed YAML tree."""
    if isinstance(raw, str):
        def repl(m: re.Match[str]) -> str:
            name = m.group(1)
            val = os.environ.get(name)
            if val is None:
                raise EnvVarMissingError(f"env var '{name}' referenced in config is not set")
            return val
        return _ENV_VAR_RE.sub(repl, raw)
    if isinstance(raw, dict):
        return {k: _substitute_env(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_substitute_env(v) for v in raw]
    return raw
```

Now update `load_config` to call it (replace the existing `load_config` body):

```python
def load_config(path: str | Path) -> Config:
    """Parse and validate a YAML config file. Raises ConfigError on any failure."""
    p = Path(path)
    try:
        raw: Any = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: top-level YAML must be a mapping")
    try:
        raw = _substitute_env(raw)
    except EnvVarMissingError as e:
        raise ConfigError(f"{p}: {e}") from e
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"{p}: schema validation failed:\n{e}") from e
```

(Also remove the now-duplicate `import os`/`import re` lines that came from earlier tasks if any; the `from sdac.errors import EnvVarMissingError` extends the existing `from sdac.errors import ConfigError` line.)

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_config.py -v -k env_var`
Expected: 3 passing.

- [ ] **Step 6: Full check**

Run: `pytest -q && ruff check src tests && mypy src`
Expected: all clean, 9 tests passing.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/config.py tests/unit/test_config.py tests/fixtures/configs/env_var.yaml
git commit -m "feat(config): \${ENV_VAR} substitution with missing-var diagnostic"
```

---

## Task 6: Config — file mode warning (warn-only by default)

**Files:**
- Modify: `src/sdac/config.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/unit/test_config.py
import stat


def test_strict_perms_rejects_world_readable(tmp_path: Path):
    p = tmp_path / "open.yaml"
    p.write_text("version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
                 "pages:\n      p:\n        keys: {}\n")
    p.chmod(0o644)
    from sdac.errors import ConfigPermissionError
    with pytest.raises(ConfigPermissionError):
        load_config(p, strict_perms=True)


def test_loose_perms_emit_warning(tmp_path: Path, recwarn):
    p = tmp_path / "open.yaml"
    p.write_text("version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
                 "pages:\n      p:\n        keys: {}\n")
    p.chmod(0o644)
    load_config(p)  # warn-only by default
    assert any("0644" in str(w.message) or "permissions" in str(w.message).lower() for w in recwarn.list)


def test_strict_perms_passes_on_0600(tmp_path: Path):
    p = tmp_path / "closed.yaml"
    p.write_text("version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
                 "pages:\n      p:\n        keys: {}\n")
    p.chmod(0o600)
    load_config(p, strict_perms=True)  # no exception
```

Note for Windows: chmod is a no-op. The test should skip on Windows.

Add at the top of test_config.py:
```python
import sys
WINDOWS = sys.platform.startswith("win")
```

Decorate the three perms tests with:
```python
@pytest.mark.skipif(WINDOWS, reason="POSIX permission semantics only")
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/unit/test_config.py -v -k perms`
Expected: failing (no `strict_perms` kwarg yet).

- [ ] **Step 3: Implement** — modify `load_config` signature and add helper

Replace `load_config` in `src/sdac/config.py`:

```python
def load_config(path: str | Path, *, strict_perms: bool = False) -> Config:
    """Parse and validate a YAML config file.

    Args:
        path: Path to the YAML file.
        strict_perms: When True, raise ConfigPermissionError if the file is
            readable by group or others (POSIX only). Default is warn-only.

    Raises:
        ConfigError, ConfigPermissionError, EnvVarMissingError.
    """
    p = Path(path)
    _check_perms(p, strict=strict_perms)
    try:
        raw: Any = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: top-level YAML must be a mapping")
    try:
        raw = _substitute_env(raw)
    except EnvVarMissingError as e:
        raise ConfigError(f"{p}: {e}") from e
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"{p}: schema validation failed:\n{e}") from e
```

Add helper:

```python
import sys
import warnings

from sdac.errors import ConfigPermissionError


def _check_perms(path: Path, *, strict: bool) -> None:
    """POSIX-only permission check. No-op on Windows."""
    if sys.platform.startswith("win"):
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        msg = (
            f"{path}: permissions are 0{mode:o}; recommended 0600 to keep secrets safe."
        )
        if strict:
            raise ConfigPermissionError(msg)
        warnings.warn(msg, stacklevel=2)
```

(Top-of-file imports may need consolidating; merge the imports cleanly.)

Extend `sdac.errors` import in `config.py`:
```python
from sdac.errors import ConfigError, ConfigPermissionError, EnvVarMissingError
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_config.py -v -k perms`
Expected: 3 passing.

- [ ] **Step 5: Full check**

Run: `pytest -q && ruff check src tests && mypy src`
Expected: clean, 12 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/config.py tests/unit/test_config.py
git commit -m "feat(config): warn-only file permission check, strict mode opt-in"
```

---

## Task 7: CLI — wire `sdac validate`

**Files:**
- Modify: `src/sdac/cli.py`
- Modify: `tests/unit/test_cli.py`
- Create: `tests/fixtures/configs/invalid_schema.yaml`

- [ ] **Step 1: Write `tests/fixtures/configs/invalid_schema.yaml`**

```yaml
version: 1
default_profile: ghost
profiles:
  coding:
    default_page: home
    pages:
      home:
        keys: {}
```

- [ ] **Step 2: Write failing tests**

```python
# Append to tests/unit/test_cli.py
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_validate_minimal_succeeds():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "minimal.yaml")])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_invalid_exits_nonzero_with_error():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "invalid_schema.yaml")])
    assert result.exit_code != 0
    assert "default_profile" in result.output


def test_validate_comprehensive_succeeds():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "comprehensive.yaml")])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 3: Run failing tests**

Run: `pytest tests/unit/test_cli.py -v -k validate`
Expected: failing (`validate` still raises `UsageError`).

- [ ] **Step 4: Implement** — replace the `validate` body in `src/sdac/cli.py`

```python
import sys

from sdac.config import load_config
from sdac.errors import ConfigError


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--strict-perms", is_flag=True, help="Reject files with permissions wider than 0600 (POSIX only).")
def validate(config_path: str, strict_perms: bool) -> None:
    """Validate a config file."""
    try:
        cfg = load_config(config_path, strict_perms=strict_perms)
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    n_profiles = len(cfg.profiles)
    n_keys = sum(
        len(page.keys)
        for p in cfg.profiles.values()
        for page in p.pages.values()
    )
    click.echo(f"OK: {config_path} ({n_profiles} profile(s), {n_keys} key(s) configured)")
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_cli.py -v -k validate`
Expected: 3 passing.

- [ ] **Step 6: Manual smoke**

Run: `sdac validate tests/fixtures/configs/comprehensive.yaml`
Expected: `OK: tests/fixtures/configs/comprehensive.yaml (2 profile(s), N key(s) configured)`

- [ ] **Step 7: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py tests/fixtures/configs/invalid_schema.yaml
git commit -m "feat(cli): wire sdac validate"
```

---

## Task 8: Renderer — text + bg color (golden test infrastructure)

**Files:**
- Create: `src/sdac/render.py`
- Create: `tests/unit/test_render.py`
- Add: `src/sdac/assets/fonts/Inter-Bold.ttf` (download in Step 1)
- Pre-create: `tests/fixtures/goldens/.gitkeep`

- [ ] **Step 1: Download the bundled font**

```bash
mkdir -p src/sdac/assets/fonts tests/fixtures/goldens
curl -fsSL -o src/sdac/assets/fonts/Inter-Bold.ttf \
  https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Bold.ttf
echo "Inter-Bold $(stat -c %s src/sdac/assets/fonts/Inter-Bold.ttf) bytes"
touch tests/fixtures/goldens/.gitkeep
```

Expected: file is ~310KB.

- [ ] **Step 2: Write `tests/unit/test_render.py` (golden-driven, with regen escape hatch)**

```python
"""Renderer tests. Uses golden images.

Regenerate goldens by running:
    SDAC_REGEN=1 pytest tests/unit/test_render.py
Review the resulting PNGs in tests/fixtures/goldens/ before committing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from sdac.config import IconSpec, KeyConfig, ShellAction
from sdac.render import KEY_SIZE, render_key

GOLDENS = Path(__file__).parent.parent / "fixtures" / "goldens"
REGEN = os.environ.get("SDAC_REGEN") == "1"


def _assert_matches_golden(img: Image.Image, name: str) -> None:
    target = GOLDENS / name
    if REGEN or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target)
        if not REGEN:
            pytest.fail(f"Golden {target} created (was missing). Re-run tests to verify.")
        return
    expected = Image.open(target).convert("RGB")
    diff = ImageChops.difference(img.convert("RGB"), expected)
    assert diff.getbbox() is None, f"image does not match golden {target}"


def _key(icon: IconSpec) -> KeyConfig:
    return KeyConfig(icon=icon, action=ShellAction(type="shell", cmd="true"))


def test_text_only_blue_bg():
    k = _key(IconSpec(text="Tests", bg="#1e88e5"))
    img = render_key(k, state="idle")
    assert img.size == (KEY_SIZE, KEY_SIZE)
    assert img.mode == "RGB"
    _assert_matches_golden(img, "text_only_blue.png")
```

- [ ] **Step 3: Run test to see failure**

Run: `pytest tests/unit/test_render.py -v`
Expected: ImportError on `sdac.render`.

- [ ] **Step 4: Implement minimal `src/sdac/render.py`** (text + bg only)

```python
"""Pillow-based icon renderer.

Produces 72×72 RGB images suitable for the Stream Deck MK.2 (which expects
72×72 JPEG; conversion happens at device-push time in a later phase).

Pure: takes a KeyConfig + state, returns a PIL Image. No file I/O except
loading bundled fonts and user-specified image references.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from sdac.config import IconSpec, KeyConfig
from sdac.errors import RenderError

KEY_SIZE = 72  # MK.2 spec
DEFAULT_BG = "#000000"
DEFAULT_FG = "#ffffff"
FONT_PATH = files("sdac.assets.fonts").joinpath("Inter-Bold.ttf")

State = Literal["idle", "active", "pressed", "error", "disconnected"]


def _bg_color(icon: IconSpec, state: State) -> str:
    """Resolve background color for a given state, with fallback chain."""
    match state:
        case "idle":
            return icon.bg_idle or icon.bg or DEFAULT_BG
        case "active":
            return icon.bg_active or icon.bg_idle or icon.bg or DEFAULT_BG
        case "pressed":
            return icon.bg_pressed or icon.bg_idle or icon.bg or DEFAULT_BG
        case "error":
            return icon.bg_error or "#b71c1c"
        case "disconnected":
            return icon.bg_disconnected or "#424242"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        with FONT_PATH.open("rb") as f:
            return ImageFont.truetype(f, size=size)
    except OSError as e:
        raise RenderError(f"cannot load bundled font: {e}") from e


def render_key(key: KeyConfig, *, state: State = "idle") -> Image.Image:
    """Render a single key icon at native MK.2 resolution."""
    bg = _bg_color(key.icon, state)
    fg = key.icon.fg or DEFAULT_FG
    img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), bg)
    draw = ImageDraw.Draw(img)
    if key.icon.text:
        _draw_text(draw, key.icon.text, fg)
    return img


def _draw_text(draw: ImageDraw.ImageDraw, text: str, fg: str) -> None:
    """Draw centered, auto-sized text within KEY_SIZE."""
    # Try sizes from 18 down to 9 until the text fits with 4px padding.
    for size in range(18, 8, -1):
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= KEY_SIZE - 8 and h <= KEY_SIZE - 8:
            x = (KEY_SIZE - w) // 2 - bbox[0]
            y = (KEY_SIZE - h) // 2 - bbox[1]
            draw.text((x, y), text, fill=fg, font=font)
            return
    # Fallback to smallest size, truncated.
    font = _load_font(9)
    draw.text((4, 4), text[:8], fill=fg, font=font)
```

- [ ] **Step 5: Run test — should create the golden on first run, then fail telling you to re-run**

Run: `pytest tests/unit/test_render.py -v`
Expected: test fails the first time with "Golden ... created (was missing). Re-run tests to verify."

- [ ] **Step 6: Re-run — golden now exists, test passes**

Run: `pytest tests/unit/test_render.py -v`
Expected: PASS.

- [ ] **Step 7: Inspect the golden**

Run: `xdg-open tests/fixtures/goldens/text_only_blue.png`
Expected: 72×72 blue tile with white centered "Tests" text.

- [ ] **Step 8: Commit**

```bash
git add src/sdac/render.py src/sdac/assets/fonts/Inter-Bold.ttf \
        tests/unit/test_render.py tests/fixtures/goldens/text_only_blue.png \
        tests/fixtures/goldens/.gitkeep
git commit -m "feat(render): text + bg color icon rendering with golden test infra"
```

---

## Task 9: Renderer — emoji support via Pilmoji

**Files:**
- Modify: `src/sdac/render.py`
- Modify: `tests/unit/test_render.py`

- [ ] **Step 1: Add failing test**

```python
# Append to tests/unit/test_render.py
def test_text_with_emoji():
    k = _key(IconSpec(text="Tests", emoji="🧪", bg="#1e88e5"))
    img = render_key(k, state="idle")
    _assert_matches_golden(img, "text_emoji_blue.png")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/test_render.py::test_text_with_emoji -v`
Expected: golden does not exist yet OR (if implemented but renders wrong) test fails on diff.

- [ ] **Step 3: Implement emoji rendering**

Replace the body of `render_key` and add `_draw_emoji_and_text` in `src/sdac/render.py`:

```python
from pilmoji import Pilmoji


def render_key(key: KeyConfig, *, state: State = "idle") -> Image.Image:
    """Render a single key icon at native MK.2 resolution."""
    bg = _bg_color(key.icon, state)
    fg = key.icon.fg or DEFAULT_FG
    img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), bg)
    if key.icon.emoji and key.icon.text:
        _draw_emoji_and_text(img, key.icon.emoji, key.icon.text, fg)
    elif key.icon.emoji:
        _draw_emoji_only(img, key.icon.emoji)
    elif key.icon.text:
        _draw_text(ImageDraw.Draw(img), key.icon.text, fg)
    return img


def _draw_emoji_only(img: Image.Image, emoji: str) -> None:
    with Pilmoji(img) as p:
        # Emoji centered at 40px
        size = 40
        # Pilmoji's getsize via internal cache; compute via emoji glyph
        bbox = p.getsize(emoji, size=size)
        x = (KEY_SIZE - bbox[0]) // 2
        y = (KEY_SIZE - bbox[1]) // 2
        p.text((x, y), emoji, font=_load_font(size), emoji_position_offset=(0, 0))


def _draw_emoji_and_text(img: Image.Image, emoji: str, text: str, fg: str) -> None:
    """Layout: emoji on top half, text on bottom half."""
    # Emoji
    with Pilmoji(img) as p:
        emoji_size = 28
        bbox = p.getsize(emoji, size=emoji_size)
        x = (KEY_SIZE - bbox[0]) // 2
        y = 6
        p.text((x, y), emoji, font=_load_font(emoji_size))
    # Text
    draw = ImageDraw.Draw(img)
    for size in range(14, 8, -1):
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= KEY_SIZE - 4 and h <= 22:
            x = (KEY_SIZE - w) // 2 - bbox[0]
            y = KEY_SIZE - h - 6 - bbox[1]
            draw.text((x, y), text, fill=fg, font=font)
            return
    font = _load_font(9)
    draw.text((4, KEY_SIZE - 14), text[:7], fill=fg, font=font)
```

(Pilmoji requires the Pillow image to be RGB or RGBA. It fetches Twemoji PNGs at runtime; cache lives in pilmoji's default location. For CI we accept the network dependency; offline support comes in a later phase.)

- [ ] **Step 4: Run test (creates golden)**

Run: `pytest tests/unit/test_render.py::test_text_with_emoji -v`
Expected: first run creates the golden + fails with message; second run passes.

- [ ] **Step 5: Inspect golden**

Run: `xdg-open tests/fixtures/goldens/text_emoji_blue.png`
Expected: blue tile, 🧪 in upper half, "Tests" below.

- [ ] **Step 6: Full check**

Run: `pytest -q && ruff check src tests && mypy src`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/render.py tests/unit/test_render.py tests/fixtures/goldens/text_emoji_blue.png
git commit -m "feat(render): emoji rendering via Pilmoji"
```

---

## Task 10: Renderer — image-background support

**Files:**
- Modify: `src/sdac/render.py`
- Modify: `tests/unit/test_render.py`
- Create: `tests/fixtures/images/test-icon.png`

- [ ] **Step 1: Create a test image**

```bash
python -c "from PIL import Image; Image.new('RGBA', (256, 256), (255, 0, 0, 255)).save('tests/fixtures/images/test-icon.png')"
```

- [ ] **Step 2: Add failing test**

```python
# Append to tests/unit/test_render.py
def test_image_background_centered_and_scaled():
    img_path = Path(__file__).parent.parent / "fixtures" / "images" / "test-icon.png"
    k = _key(IconSpec(image=str(img_path), bg="#222222"))
    img = render_key(k, state="idle")
    _assert_matches_golden(img, "image_background.png")
```

- [ ] **Step 3: Run failing test**

Run: `pytest tests/unit/test_render.py::test_image_background_centered_and_scaled -v`
Expected: either AttributeError (image field unused) or golden-missing failure.

- [ ] **Step 4: Implement image support**

Extend `render_key`:

```python
def render_key(key: KeyConfig, *, state: State = "idle") -> Image.Image:
    """Render a single key icon at native MK.2 resolution."""
    bg = _bg_color(key.icon, state)
    fg = key.icon.fg or DEFAULT_FG
    img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), bg)
    if key.icon.image:
        _composite_image(img, key.icon.image)
    if key.icon.emoji and key.icon.text:
        _draw_emoji_and_text(img, key.icon.emoji, key.icon.text, fg)
    elif key.icon.emoji:
        _draw_emoji_only(img, key.icon.emoji)
    elif key.icon.text:
        _draw_text(ImageDraw.Draw(img), key.icon.text, fg)
    return img


def _composite_image(canvas: Image.Image, path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise RenderError(f"icon image not found: {p}")
    try:
        src = Image.open(p).convert("RGBA")
    except OSError as e:
        raise RenderError(f"cannot read icon image {p}: {e}") from e
    src.thumbnail((KEY_SIZE - 8, KEY_SIZE - 8), Image.Resampling.LANCZOS)
    x = (KEY_SIZE - src.width) // 2
    y = (KEY_SIZE - src.height) // 2
    canvas.paste(src, (x, y), src)
```

- [ ] **Step 5: Run test**

Run: `pytest tests/unit/test_render.py::test_image_background_centered_and_scaled -v`
Expected: creates golden, then passes on second run.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/render.py tests/unit/test_render.py \
        tests/fixtures/images/test-icon.png tests/fixtures/goldens/image_background.png
git commit -m "feat(render): image-background support"
```

---

## Task 11: Renderer — state variants

**Files:**
- Modify: `tests/unit/test_render.py`

- [ ] **Step 1: Add four tests**

```python
# Append to tests/unit/test_render.py
def test_state_active_uses_bg_active():
    k = _key(IconSpec(text="REC", bg_idle="#424242", bg_active="#d32f2f"))
    img = render_key(k, state="active")
    _assert_matches_golden(img, "state_active.png")


def test_state_pressed_falls_back_to_idle_when_unspecified():
    k = _key(IconSpec(text="Build", bg="#43a047"))
    img = render_key(k, state="pressed")
    _assert_matches_golden(img, "state_pressed.png")


def test_state_error_uses_default_red_when_unspecified():
    k = _key(IconSpec(text="Err", bg="#1e88e5"))
    img = render_key(k, state="error")
    _assert_matches_golden(img, "state_error.png")


def test_state_disconnected_uses_default_gray():
    k = _key(IconSpec(text="Off", bg="#1e88e5"))
    img = render_key(k, state="disconnected")
    _assert_matches_golden(img, "state_disconnected.png")
```

- [ ] **Step 2: Run — Pillow logic is already in place from Task 8; tests just need their goldens**

Run: `pytest tests/unit/test_render.py -k state -v`
Expected: goldens created; second run passes.

- [ ] **Step 3: Visually inspect all four**

Run: `for f in tests/fixtures/goldens/state_*.png; do echo $f; done`
Expected: idle/active/pressed/error/disconnected all distinct.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_render.py tests/fixtures/goldens/state_*.png
git commit -m "test(render): state variant goldens"
```

---

## Task 12: Renderer — `render_mosaic` for `sdac preview`

**Files:**
- Modify: `src/sdac/render.py`
- Modify: `tests/unit/test_render.py`

- [ ] **Step 1: Add failing test**

```python
# Append to tests/unit/test_render.py
from sdac.config import load_config
from sdac.render import KEY_SIZE, MK2_COLS, MK2_ROWS, render_mosaic

MOSAIC_W = KEY_SIZE * MK2_COLS + (MK2_COLS - 1) * 8
MOSAIC_H = KEY_SIZE * MK2_ROWS + (MK2_ROWS - 1) * 8


def test_render_mosaic_dimensions():
    cfg = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "comprehensive.yaml")
    page = cfg.profiles["coding"].pages["home"]
    img = render_mosaic(page)
    assert img.size == (MOSAIC_W, MOSAIC_H)
    assert img.mode == "RGB"


def test_render_mosaic_empty_keys_are_blank():
    cfg = load_config(Path(__file__).parent.parent / "fixtures" / "configs" / "minimal.yaml")
    page = cfg.profiles["coding"].pages["home"]
    img = render_mosaic(page)
    # All keys are unconfigured → solid black mosaic
    assert img.getpixel((0, 0)) == (0, 0, 0)
    assert img.getpixel((MOSAIC_W - 1, MOSAIC_H - 1)) == (0, 0, 0)
```

- [ ] **Step 2: Run failing**

Run: `pytest tests/unit/test_render.py -k mosaic -v`
Expected: ImportError on `MK2_COLS`/`MK2_ROWS`/`render_mosaic`.

- [ ] **Step 3: Implement** — add to `src/sdac/render.py`

```python
from sdac.config import PageConfig

MK2_COLS = 5
MK2_ROWS = 3
MOSAIC_GAP = 8
PLACEHOLDER_BG = "#000000"


def render_mosaic(page: PageConfig, *, state: State = "idle") -> Image.Image:
    """Compose every key on a page into a single mosaic image. Empty slots render as black."""
    w = KEY_SIZE * MK2_COLS + (MK2_COLS - 1) * MOSAIC_GAP
    h = KEY_SIZE * MK2_ROWS + (MK2_ROWS - 1) * MOSAIC_GAP
    canvas = Image.new("RGB", (w, h), PLACEHOLDER_BG)
    for idx in range(MK2_COLS * MK2_ROWS):
        row = idx // MK2_COLS
        col = idx % MK2_COLS
        x = col * (KEY_SIZE + MOSAIC_GAP)
        y = row * (KEY_SIZE + MOSAIC_GAP)
        key = page.keys.get(idx)
        if key is not None:
            tile = render_key(key, state=state)
            canvas.paste(tile, (x, y))
    return canvas
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_render.py -k mosaic -v`
Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add src/sdac/render.py tests/unit/test_render.py
git commit -m "feat(render): render_mosaic for offline preview"
```

---

## Task 13: CLI — wire `sdac preview`

**Files:**
- Modify: `src/sdac/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/unit/test_cli.py
def test_preview_writes_png(tmp_path: Path):
    out = tmp_path / "preview.png"
    runner = CliRunner()
    result = runner.invoke(main, [
        "preview", str(FIXTURES / "comprehensive.yaml"),
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.stat().st_size > 1024  # at least a kilobyte of PNG


def test_preview_respects_profile_and_page(tmp_path: Path):
    out = tmp_path / "stream.png"
    runner = CliRunner()
    result = runner.invoke(main, [
        "preview", str(FIXTURES / "comprehensive.yaml"),
        "--profile", "streaming",
        "--page", "home",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_preview_unknown_profile_errors(tmp_path: Path):
    out = tmp_path / "x.png"
    runner = CliRunner()
    result = runner.invoke(main, [
        "preview", str(FIXTURES / "comprehensive.yaml"),
        "--profile", "ghost",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert "ghost" in result.output
```

- [ ] **Step 2: Run failing**

Run: `pytest tests/unit/test_cli.py -k preview -v`
Expected: `UsageError("not implemented yet")`.

- [ ] **Step 3: Implement** — replace `preview` in `src/sdac/cli.py`

```python
from sdac.render import render_mosaic


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--out", type=click.Path(dir_okay=False, writable=True), default="preview.png")
@click.option("--profile", default=None, help="Profile name to preview. Defaults to default_profile.")
@click.option("--page", default=None, help="Page name to preview. Defaults to the profile's default_page.")
def preview(config_path: str, out: str, profile: str | None, page: str | None) -> None:
    """Render a profile/page as a mosaic PNG."""
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    pname = profile or cfg.default_profile
    if pname not in cfg.profiles:
        click.echo(f"unknown profile: {pname}", err=True)
        sys.exit(3)
    p = cfg.profiles[pname]
    page_name = page or p.default_page
    if page_name not in p.pages:
        click.echo(f"unknown page: {page_name} in profile {pname}", err=True)
        sys.exit(4)
    img = render_mosaic(p.pages[page_name])
    img.save(out)
    click.echo(f"Wrote {out} ({img.width}×{img.height})")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_cli.py -k preview -v`
Expected: 3 passing.

- [ ] **Step 5: Manual smoke**

Run: `sdac preview tests/fixtures/configs/comprehensive.yaml --out /tmp/sd-preview.png && xdg-open /tmp/sd-preview.png`
Expected: a PNG mosaic of the coding/home page with real icons.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): wire sdac preview to render_mosaic"
```

---

## Task 14: CI on Ubuntu and Windows

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, windows-2022]
        python: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      - name: Install
        run: pip install -e ".[dev]"
      - name: Lint
        run: ruff check src tests
      - name: Type check
        run: mypy src
      - name: Tests
        env:
          # Pilmoji fetches Twemoji from GitHub on first run; cache in CI is per-job ephemeral.
          PILMOJI_USE_CACHE: "1"
        run: pytest -q --cov=sdac --cov-report=term-missing
```

- [ ] **Step 2: Validate locally with `act` if available, otherwise inspect manually**

Run: `cat .github/workflows/ci.yml`
Expected: file is valid YAML.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint + type + tests on Ubuntu + Windows matrix"
```

---

## Task 15: README + schema reference doc

**Files:**
- Modify: `README.md`
- Create: `docs/schema.md`

- [ ] **Step 1: Full README** — replace `README.md` placeholder with:

```markdown
# streamdeck-as-code

Cross-platform declarative driver for the Elgato Stream Deck. One YAML config produces identical behavior on Linux and Windows; later phases ship a daemon that talks to the device directly over USB HID with live OBS state integration.

**Status:** Phase 1 (current). `sdac validate` + `sdac preview` work without a USB device. Daemon, OBS integration, and Windows-specific watchers land in Phases 2–4.

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
# 1. Write a config (or copy from examples/)
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
Wrote preview.png (392×232)
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

Phase 1 targets the Elgato Stream Deck MK.2 (15 keys, 72×72 JPEG per key). Architecture is hardware-agnostic; XL/Mini/Plus support is queued for a later phase.

## Development

```bash
git clone https://github.com/solomonneas/streamdeck-as-code
cd streamdeck-as-code
python3.11 -m venv .venv && . .venv/bin/activate
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
```

- [ ] **Step 2: Write `docs/schema.md`**

```markdown
# YAML schema reference (v1)

See [`tests/fixtures/configs/comprehensive.yaml`](../tests/fixtures/configs/comprehensive.yaml) for a working example.

## Top level

```yaml
version: 1
default_profile: <profile-name>
vars: { <key>: <value> }                # optional, available as {{vars.key}} in actions (resolved at execute-time in Phase 2)
obs_hosts:                              # optional in Phase 1, required in Phase 3
  <name>:
    url: obsws://<host>:<port>/<password-or-${ENV_VAR}>
profile_rules:                          # optional, used by Phase 4 active-window watcher
  - profile: <profile>
    when:
      app_class: [...]                  # Linux WM_CLASS
      app_name:  [...]                  # Windows process names
profiles:
  <profile-name>: <Profile>
```

## Profile

```yaml
default_page: <page-name>
pages:
  <page-name>: <Page>
```

## Page

```yaml
keys:
  <index 0..14>: <Key>
```

## Key

```yaml
icon: <IconSpec>
action: <Action>      # one of 21 types, discriminator: `type`
indicator: <Indicator?>  # optional live state binding
```

## IconSpec

```yaml
text: <str?>
emoji: <str?>          # any unicode emoji
image: <path?>         # path resolved relative to the config file
bg: "#rrggbb"          # default background
bg_idle: ...           # alias for bg, takes precedence
bg_active: ...         # used when bound indicator is true
bg_pressed: ...        # used briefly after press
bg_error: ...          # used on action failure (default #b71c1c)
bg_disconnected: ...   # used when an OBS host is unreachable (default #424242)
fg: "#rrggbb"          # text color (default #ffffff)
```

At least one of `text`, `emoji`, `image` must be set.

## Actions

| `type` | Required fields | Optional |
|---|---|---|
| `shell` | `cmd` | `cwd`, `shell` |
| `key.chord` | `keys` | — |
| `key.text` | `text` | — |
| `open.url` | `url` | — |
| `open.app` | exactly one of `path`/`name` | — |
| `obs.scene.switch` | `host`, `scene` | — |
| `obs.recording.toggle`, `obs.streaming.toggle`, `obs.replay.save`, `obs.virtualcam.toggle` | `host` | — |
| `obs.input.mute.toggle` | `host`, `input_name` | — |
| `system.volume.up`/`down` | — | `step` (default 5) |
| `system.volume.mute`, `media.play`, `media.pause`, `media.next`, `media.prev` | — | — |
| `page.go` | `page` | — |
| `profile.switch` | `profile` | — |
| `compound` | `actions: [Action]` | `continue_on_error` (bool) |

## Indicator (live state binding, Phase 3+)

```yaml
bind: obs.recording.state | obs.streaming.state | obs.replay.state |
      obs.virtualcam.state | obs.scene.current | obs.input.muted
host: <obs_host name>
scene: <scene name?>      # required with obs.scene.current
input_name: <str?>        # required with obs.input.muted
```

When the bound source is "active", the key renders with the `active` state variant (uses `bg_active`).

## Environment variable substitution

Any string field can include `${VAR_NAME}`. Resolution happens before schema validation. Missing variables raise `ConfigError`. Recommended for OBS passwords.

```yaml
obs_hosts:
  roc:
    url: obsws://127.0.0.1:4455/${SDAC_OBS_ROC_PASS}
```

## File permissions

On POSIX, `sdac` warns when the config file is readable by group or others (mode bits `0o077`). Pass `--strict-perms` to reject instead. Recommended: `chmod 0600`.
```

- [ ] **Step 3: Verify README links resolve**

Run: `grep -n 'docs/schema.md\|LICENSE\|tests/fixtures/configs/comprehensive.yaml' README.md docs/schema.md`
Expected: paths resolvable.

- [ ] **Step 4: Final full test run**

Run: `pytest -q && ruff check src tests && mypy src`
Expected: clean, all tests passing.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/schema.md
git commit -m "docs: README + YAML schema reference for Phase 1"
```

---

## Done criteria for Phase 1

1. `pipx install -e .` from the repo succeeds.
2. `sdac --version` prints `0.1.0`.
3. `sdac validate tests/fixtures/configs/comprehensive.yaml` exits 0 with an OK line.
4. `sdac preview tests/fixtures/configs/comprehensive.yaml --out /tmp/x.png` writes a valid PNG.
5. `pytest -q` passes; `ruff check src tests` clean; `mypy src` clean.
6. CI green on Ubuntu and Windows.
7. README + `docs/schema.md` accurately describe the v1 schema.
8. No `${ENV_VAR}` regressions: env-substitution tests pass.

## Out of scope (deferred to Phase 2+)

- USB HID communication and device discovery.
- Daemon loop, key-press dispatch, action execution.
- OBS WebSocket subscription and live state binding.
- Active-window watcher (Linux X11 + Windows User32).
- systemd / Task Scheduler service install.
- udev rule install.
- Multi-device support.
- macOS, Wayland, Stream Deck XL / Mini / Plus.

These are tracked in the spec's "Migration / rollout" section, Phases 2-6.
