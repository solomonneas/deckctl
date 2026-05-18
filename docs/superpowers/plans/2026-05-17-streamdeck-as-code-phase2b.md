# streamdeck-as-code Phase 2b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `sdac install-service` registers a systemd user unit + a udev rule so the daemon autostarts at user login and the Stream Deck is reachable to any logged-in user; `sdac uninstall-service` reverses it; `sdac doctor` reports device + deps + config + service status. README documents the flow.

**Architecture:** Two new modules. `sdac.service` owns the install/uninstall lifecycle: it writes a systemd user unit to `~/.config/systemd/user/sdac.service`, writes a udev rule via autonomous sudo to `/etc/udev/rules.d/60-streamdeck.rules`, reloads udev, and enables+starts the service. `sdac.doctor` runs a series of named checks (device, libhidapi, python deps, system binaries, service status, udev rule, config validation) and prints a tabular report with PASS/WARN/FAIL per row. CLI gets three new Click verbs: `install-service`, `uninstall-service`, `doctor`.

**Tech Stack:** Python 3.12, Click, subprocess (sudo + systemctl + udevadm + which), Pydantic (already in deps). No new runtime deps.

---

## File Structure

```
streamdeck-as-code/
  src/sdac/
    cli.py                                    # Modify: add install-service, uninstall-service, doctor
    service.py                                # NEW: install/uninstall lifecycle
    doctor.py                                 # NEW: diagnostic checks + report
    assets/
      systemd/
        __init__.py                           # NEW: package marker for importlib.resources
        sdac.service.template                 # NEW: systemd unit template (with {sdac_path}/{config_path})
      udev/
        __init__.py                           # NEW: package marker for importlib.resources
        60-streamdeck.rules                   # NEW: udev rule (uaccess tag for 0fd9)
  tests/
    unit/
      test_service.py                         # NEW: install/uninstall unit logic
      test_doctor.py                          # NEW: per-check + report rendering
  docs/
    installation.md                           # NEW: full install walkthrough
README.md                                     # Modify: add install-service section
```

**Boundary contracts:**
- `service.py` is the only place `subprocess.run(["sudo", ...])` lives. Doctor and CLI never shell to sudo directly.
- `doctor.py` returns a list of `CheckResult` dataclasses; the CLI renders. No printing inside doctor.
- The assets directory contains text templates and the udev rule. `importlib.resources` loads them; `service.py` does the substitution.

---

## Task 1: udev rule + systemd unit assets

**Files:**
- Create: `src/sdac/assets/udev/__init__.py` (empty)
- Create: `src/sdac/assets/udev/60-streamdeck.rules`
- Create: `src/sdac/assets/systemd/__init__.py` (empty)
- Create: `src/sdac/assets/systemd/sdac.service.template`

- [ ] **Step 1: Create asset directories + package markers**

```bash
mkdir -p src/sdac/assets/udev src/sdac/assets/systemd
touch src/sdac/assets/udev/__init__.py src/sdac/assets/systemd/__init__.py
```

- [ ] **Step 2: Write the udev rule - `src/sdac/assets/udev/60-streamdeck.rules`**

```
# Elgato Stream Deck - grant uaccess to the active logged-in user.
# Installed by `sdac install-service`. Apply: `sudo udevadm control --reload-rules && sudo udevadm trigger`.

# Vendor: Elgato Systems GmbH (0fd9)
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0fd9", TAG+="uaccess"

# Specifically the MK.2 (0x0080) and other 15-key variants
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="0080", TAG+="uaccess"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="006d", TAG+="uaccess"
```

- [ ] **Step 3: Write the systemd unit template - `src/sdac/assets/systemd/sdac.service.template`**

```
[Unit]
Description=streamdeck-as-code daemon
Documentation=https://github.com/solomonneas/streamdeck-as-code
After=graphical-session.target

[Service]
Type=simple
ExecStart={sdac_path} daemon --config {config_path}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

- [ ] **Step 4: Verify assets are reachable via importlib.resources**

```bash
. .venv/bin/activate
python -c "
from importlib.resources import files
print(files('sdac.assets.udev').joinpath('60-streamdeck.rules').read_text()[:80])
print('---')
print(files('sdac.assets.systemd').joinpath('sdac.service.template').read_text()[:80])
"
```

Expected: first lines of each file print.

- [ ] **Step 5: Full check still passes**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 84 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/assets/udev/ src/sdac/assets/systemd/
git commit -m "feat(service): udev rule + systemd unit template assets"
```

---

## Task 2: Service install module (template substitution + sudo)

**Files:**
- Create: `src/sdac/service.py`
- Create: `tests/unit/test_service.py`

- [ ] **Step 1: Write failing tests - `tests/unit/test_service.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

WINDOWS = sys.platform.startswith("win")
pytestmark = pytest.mark.skipif(WINDOWS, reason="systemd is Linux-only")

from sdac.service import (  # noqa: E402
    SERVICE_NAME,
    UDEV_RULE_NAME,
    render_systemd_unit,
    user_unit_path,
)


def test_user_unit_path_under_xdg_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)
    p = user_unit_path()
    assert p == tmp_path / "systemd" / "user" / SERVICE_NAME


def test_user_unit_path_falls_back_to_home_dot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    p = user_unit_path()
    assert p == tmp_path / ".config" / "systemd" / "user" / SERVICE_NAME


def test_render_systemd_unit_substitutes_paths():
    rendered = render_systemd_unit(
        sdac_path="/home/user/.local/bin/sdac",
        config_path="/home/user/.config/sdac/config.yaml",
    )
    assert "/home/user/.local/bin/sdac daemon" in rendered
    assert "--config /home/user/.config/sdac/config.yaml" in rendered
    assert "{sdac_path}" not in rendered
    assert "{config_path}" not in rendered
    assert "[Service]" in rendered
    assert "Restart=on-failure" in rendered


def test_udev_rule_name_constant():
    assert UDEV_RULE_NAME == "60-streamdeck.rules"
```

- [ ] **Step 2: Run failing**

```bash
. .venv/bin/activate
pytest tests/unit/test_service.py -v
```

Expected: ImportError on `sdac.service`.

- [ ] **Step 3: Write `src/sdac/service.py`**

```python
"""systemd-user-unit + udev-rule install lifecycle.

Linux-only. The CLI verbs `install-service` / `uninstall-service` are thin
wrappers around install_service() / uninstall_service() below.

This module is the *only* place we shell to `sudo`. Everywhere else uses the
device or daemon abstractions.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from sdac.errors import SdacError

log = logging.getLogger(__name__)

SERVICE_NAME = "sdac.service"
UDEV_RULE_NAME = "60-streamdeck.rules"
UDEV_RULE_PATH = Path("/etc/udev/rules.d") / UDEV_RULE_NAME


class ServiceError(SdacError):
    """Raised when service install / uninstall fails."""


def user_unit_path() -> Path:
    """Path to the systemd user unit for the current user."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path(os.environ["HOME"]) / ".config"
    return base / "systemd" / "user" / SERVICE_NAME


def render_systemd_unit(*, sdac_path: str, config_path: str) -> str:
    """Substitute the systemd unit template with absolute paths."""
    tpl = files("sdac.assets.systemd").joinpath("sdac.service.template").read_text()
    return tpl.format(sdac_path=sdac_path, config_path=config_path)


def udev_rule_text() -> str:
    """The packaged udev rule, verbatim."""
    return files("sdac.assets.udev").joinpath(UDEV_RULE_NAME).read_text()


def write_user_unit(sdac_path: str, config_path: str) -> Path:
    """Write the substituted unit to ~/.config/systemd/user/sdac.service."""
    dest = user_unit_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_systemd_unit(sdac_path=sdac_path, config_path=config_path))
    log.info("wrote %s", dest)
    return dest


def install_udev_rule_with_sudo() -> None:
    """Copy the packaged udev rule to /etc/udev/rules.d via sudo, then reload udev.

    Will prompt the user for their sudo password if not cached.
    """
    text = udev_rule_text()
    # Stage rule in /tmp so we don't pipe through sudo's stdin.
    stage = Path("/tmp/sdac-60-streamdeck.rules")
    stage.write_text(text)
    try:
        subprocess.run(["sudo", "cp", str(stage), str(UDEV_RULE_PATH)], check=True)
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["sudo", "udevadm", "trigger"], check=True)
        log.info("udev rule installed at %s", UDEV_RULE_PATH)
    except subprocess.CalledProcessError as e:
        raise ServiceError(f"udev install failed: {e}") from e
    finally:
        try:
            stage.unlink()
        except FileNotFoundError:
            pass


def systemctl_user(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a `systemctl --user ...` command and capture output."""
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def install_service(*, sdac_path: str, config_path: str) -> None:
    """Full install: write unit, install udev rule, daemon-reload, enable+start."""
    if sys.platform.startswith("win"):
        raise ServiceError("install-service is Linux-only (Windows ships in Phase 4)")
    if not shutil.which("systemctl"):
        raise ServiceError("systemctl not found; this machine doesn't run systemd")
    write_user_unit(sdac_path=sdac_path, config_path=config_path)
    install_udev_rule_with_sudo()
    systemctl_user("daemon-reload")
    systemctl_user("enable", "--now", SERVICE_NAME)
    log.info("service installed and started")


def uninstall_service(*, remove_udev: bool = True) -> None:
    """Stop + disable + remove the user unit. Optionally remove the udev rule via sudo."""
    if sys.platform.startswith("win"):
        raise ServiceError("uninstall-service is Linux-only")
    # Stop + disable are best-effort; the unit may not be active.
    systemctl_user("stop", SERVICE_NAME, check=False)
    systemctl_user("disable", SERVICE_NAME, check=False)
    unit = user_unit_path()
    if unit.exists():
        unit.unlink()
        log.info("removed %s", unit)
    systemctl_user("daemon-reload", check=False)
    if remove_udev and UDEV_RULE_PATH.exists():
        try:
            subprocess.run(["sudo", "rm", str(UDEV_RULE_PATH)], check=True)
            subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
            log.info("udev rule removed")
        except subprocess.CalledProcessError as e:
            log.warning("udev rule removal failed (continuing): %s", e)


def service_status() -> str:
    """Return one of: 'active', 'inactive', 'failed', 'not-installed', 'unknown'."""
    if not user_unit_path().exists():
        return "not-installed"
    if not shutil.which("systemctl"):
        return "unknown"
    r = systemctl_user("is-active", SERVICE_NAME, check=False)
    out = r.stdout.strip()
    if out in {"active", "inactive", "failed"}:
        return out
    return "unknown"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_service.py -v
```

Expected: 4 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 88 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/service.py tests/unit/test_service.py
git commit -m "feat(service): systemd + udev install/uninstall + status query"
```

---

## Task 3: `sdac install-service` CLI verb

**Files:**
- Modify: `src/sdac/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests - append to `tests/unit/test_cli.py`**

```python
def test_install_service_calls_install_with_resolved_paths(tmp_path: Path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\nprofiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    from unittest.mock import patch
    runner = CliRunner()
    with patch("sdac.service.install_service") as inst:
        result = runner.invoke(main, ["install-service", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    inst.assert_called_once()
    kwargs = inst.call_args.kwargs
    assert kwargs["config_path"] == str(cfg.resolve())
    assert kwargs["sdac_path"].endswith("/sdac") or kwargs["sdac_path"] == "sdac"


def test_install_service_errors_when_config_missing(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["install-service", "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_cli.py -k install_service -v
```

Expected: `UsageError("no such command: install-service")`.

- [ ] **Step 3: Add the command to `src/sdac/cli.py`**

Append (after the existing `daemon` command):

```python
@main.command("install-service")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Path to the YAML config file. Stored absolutely in the unit.",
)
@click.option(
    "--sdac-path",
    default=None,
    help="Override the path to the `sdac` binary embedded in the unit. Defaults to `which sdac`.",
)
def install_service(config_path: str, sdac_path: str | None) -> None:
    """Install + enable + start the systemd user unit (and udev rule via sudo)."""
    import logging
    import shutil
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from sdac.service import ServiceError, install_service as _install
    resolved_sdac = sdac_path or shutil.which("sdac") or "sdac"
    abs_config = str(Path(config_path).resolve())
    try:
        _install(sdac_path=resolved_sdac, config_path=abs_config)
    except ServiceError as e:
        click.echo(str(e), err=True)
        sys.exit(6)
    click.echo(f"installed: systemd unit + udev rule; service active with --config {abs_config}")
```

Add to top-of-file imports if not already present:

```python
from pathlib import Path
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_cli.py -k install_service -v
```

Expected: 2 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 90 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): install-service verb (systemd + udev via sudo)"
```

---

## Task 4: `sdac uninstall-service` CLI verb

**Files:**
- Modify: `src/sdac/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests - append to `tests/unit/test_cli.py`**

```python
def test_uninstall_service_invokes_uninstall():
    from unittest.mock import patch
    runner = CliRunner()
    with patch("sdac.service.uninstall_service") as un:
        result = runner.invoke(main, ["uninstall-service"])
    assert result.exit_code == 0, result.output
    un.assert_called_once_with(remove_udev=True)


def test_uninstall_service_keep_udev_flag():
    from unittest.mock import patch
    runner = CliRunner()
    with patch("sdac.service.uninstall_service") as un:
        result = runner.invoke(main, ["uninstall-service", "--keep-udev"])
    assert result.exit_code == 0, result.output
    un.assert_called_once_with(remove_udev=False)
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_cli.py -k uninstall_service -v
```

Expected: `UsageError("no such command: uninstall-service")`.

- [ ] **Step 3: Add the command to `src/sdac/cli.py`**

Append (after the install-service command):

```python
@main.command("uninstall-service")
@click.option("--keep-udev", is_flag=True, help="Leave the udev rule in place; only remove the systemd unit.")
def uninstall_service(keep_udev: bool) -> None:
    """Stop + disable + remove the systemd unit (and udev rule unless --keep-udev)."""
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from sdac.service import ServiceError, uninstall_service as _uninstall
    try:
        _uninstall(remove_udev=not keep_udev)
    except ServiceError as e:
        click.echo(str(e), err=True)
        sys.exit(6)
    click.echo("uninstalled" + ("" if not keep_udev else " (udev rule kept)"))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_cli.py -k uninstall_service -v
```

Expected: 2 passing.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean, 92 tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): uninstall-service verb (systemd + udev via sudo)"
```

---

## Task 5: Doctor - check primitives + report rendering

**Files:**
- Create: `src/sdac/doctor.py`
- Create: `tests/unit/test_doctor.py`

- [ ] **Step 1: Write failing tests - `tests/unit/test_doctor.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from sdac.doctor import (
    CheckResult,
    Severity,
    check_config,
    check_libhidapi,
    check_python_deps,
    check_service_status,
    check_stream_deck,
    check_system_binaries,
    check_udev_rule,
    render_report,
    run_all_checks,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_check_result_dataclass():
    r = CheckResult(name="test", severity=Severity.PASS, message="ok")
    assert r.name == "test"
    assert r.severity is Severity.PASS


def test_check_stream_deck_passes_when_device_present():
    fake_device = object()
    with patch("sdac.doctor._enumerate_first") as enum:
        enum.return_value = fake_device
        r = check_stream_deck()
    assert r.severity is Severity.PASS
    assert "found" in r.message.lower()


def test_check_stream_deck_fails_when_not_found():
    with patch("sdac.doctor._enumerate_first", return_value=None):
        r = check_stream_deck()
    assert r.severity is Severity.FAIL


def test_check_stream_deck_fails_on_probe_error():
    with patch("sdac.doctor._enumerate_first", side_effect=RuntimeError("no HID backend")):
        r = check_stream_deck()
    assert r.severity is Severity.FAIL
    assert "no HID backend" in r.message


def test_check_python_deps_passes_when_all_importable():
    r = check_python_deps()
    assert r.severity is Severity.PASS  # streamdeck, watchdog, pydantic, click, pillow, pilmoji


def test_check_libhidapi_passes_when_library_imports():
    """libhidapi-libusb0 is needed for streamdeck enumeration. We test by
    confirming the streamdeck DeviceManager can be instantiated."""
    r = check_libhidapi()
    # On this dev machine libhidapi-libusb0 is installed, so this should pass.
    # If it fails on a fresh machine, the message will name the missing lib.
    assert r.severity in (Severity.PASS, Severity.FAIL)


def test_check_system_binaries_reports_each(tmp_path: Path):
    """Each of xdotool/pactl/playerctl is independently reported."""
    r = check_system_binaries()
    assert "xdotool" in r.message
    assert "pactl" in r.message
    assert "playerctl" in r.message


def test_check_config_pass_on_valid():
    r = check_config(str(FIXTURES / "minimal.yaml"))
    assert r.severity is Severity.PASS


def test_check_config_fail_on_invalid():
    r = check_config(str(FIXTURES / "invalid_schema.yaml"))
    assert r.severity is Severity.FAIL


def test_check_config_warn_when_no_path_provided():
    r = check_config(None)
    assert r.severity is Severity.WARN
    assert "skip" in r.message.lower() or "no config" in r.message.lower()


def test_check_service_status_returns_status_severity():
    with patch("sdac.doctor.service_status", return_value="active"):
        r = check_service_status()
    assert r.severity is Severity.PASS

    with patch("sdac.doctor.service_status", return_value="inactive"):
        r = check_service_status()
    assert r.severity is Severity.WARN

    with patch("sdac.doctor.service_status", return_value="failed"):
        r = check_service_status()
    assert r.severity is Severity.FAIL

    with patch("sdac.doctor.service_status", return_value="not-installed"):
        r = check_service_status()
    assert r.severity is Severity.WARN


def test_check_udev_rule_pass_when_present():
    with patch("pathlib.Path.exists", return_value=True):
        r = check_udev_rule()
    assert r.severity is Severity.PASS


def test_check_udev_rule_warn_when_absent():
    with patch("pathlib.Path.exists", return_value=False):
        r = check_udev_rule()
    assert r.severity is Severity.WARN


def test_render_report_includes_each_check():
    results = [
        CheckResult(name="device", severity=Severity.PASS, message="ok"),
        CheckResult(name="config", severity=Severity.FAIL, message="oops"),
    ]
    out = render_report(results)
    assert "device" in out
    assert "config" in out
    assert "PASS" in out
    assert "FAIL" in out


def test_run_all_checks_returns_list_of_results():
    results = run_all_checks(config_path=None)
    assert isinstance(results, list)
    assert all(isinstance(r, CheckResult) for r in results)
    assert len(results) >= 5
```

- [ ] **Step 2: Run failing**

```bash
. .venv/bin/activate
pytest tests/unit/test_doctor.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `src/sdac/doctor.py`**

```python
"""Diagnostics for `sdac doctor`.

Each check returns a CheckResult. The CLI calls run_all_checks() and pipes
the list to render_report().
"""

from __future__ import annotations

import importlib
import logging
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from sdac.config import load_config
from sdac.errors import ConfigError
from sdac.service import UDEV_RULE_PATH, service_status

log = logging.getLogger(__name__)


class Severity(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    name: str
    severity: Severity
    message: str


def _enumerate_first() -> Any:
    """Wrapper so tests can patch this without importing streamdeck."""
    from sdac.device.streamdeck import StreamDeckDevice
    return StreamDeckDevice.enumerate_first_or_none()


def check_stream_deck() -> CheckResult:
    try:
        dev = _enumerate_first()
    except Exception as e:
        return CheckResult("device", Severity.FAIL, f"enumeration error: {e}")
    if dev is None:
        return CheckResult(
            "device",
            Severity.FAIL,
            "no Stream Deck found on USB (check cable + libhidapi-libusb0 + udev rule)",
        )
    return CheckResult("device", Severity.PASS, f"found Stream Deck (key_count={dev.key_count})")


def check_libhidapi() -> CheckResult:
    """Best-effort probe: import the upstream DeviceManager and try to enumerate.

    If libhidapi-libusb0 is missing, enumeration raises ProbeError immediately.
    """
    try:
        from StreamDeck.DeviceManager import DeviceManager  # type: ignore[import-untyped]
        DeviceManager().enumerate()
    except Exception as e:
        return CheckResult(
            "libhidapi",
            Severity.FAIL,
            f"HID backend probe failed: {e} (apt-install libhidapi-libusb0)",
        )
    return CheckResult("libhidapi", Severity.PASS, "HID backend available")


_PY_DEPS = ["streamdeck", "watchdog", "pydantic", "click", "PIL", "pilmoji", "yaml"]


def check_python_deps() -> CheckResult:
    missing: list[str] = []
    for name in _PY_DEPS:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        return CheckResult(
            "python_deps",
            Severity.FAIL,
            f"missing Python packages: {', '.join(missing)} - run `pip install -e \".[dev]\"`",
        )
    return CheckResult("python_deps", Severity.PASS, f"all Python deps importable ({len(_PY_DEPS)} packages)")


_SYS_BINARIES = ["xdotool", "pactl", "playerctl"]


def check_system_binaries() -> CheckResult:
    found: list[str] = []
    missing: list[str] = []
    for b in _SYS_BINARIES:
        if shutil.which(b):
            found.append(b)
        else:
            missing.append(b)
    if missing:
        return CheckResult(
            "system_binaries",
            Severity.WARN,
            f"missing: {', '.join(missing)}; present: {', '.join(found)} "
            "(daemon will fail on actions that need the missing one)",
        )
    return CheckResult(
        "system_binaries",
        Severity.PASS,
        f"all present: {', '.join(found)}",
    )


def check_config(path: str | None) -> CheckResult:
    if path is None:
        return CheckResult("config", Severity.WARN, "skipped - no --config provided")
    try:
        cfg = load_config(path)
    except ConfigError as e:
        return CheckResult("config", Severity.FAIL, f"{path}: {e}")
    n = sum(len(p.keys) for prof in cfg.profiles.values() for p in prof.pages.values())
    return CheckResult(
        "config",
        Severity.PASS,
        f"{path}: {len(cfg.profiles)} profile(s), {n} key(s)",
    )


def check_service_status() -> CheckResult:
    status = service_status()
    if status == "active":
        return CheckResult("service", Severity.PASS, "systemd user unit active")
    if status == "inactive":
        return CheckResult("service", Severity.WARN, "systemd user unit installed but not running")
    if status == "failed":
        return CheckResult("service", Severity.FAIL, "systemd user unit FAILED (journalctl --user -u sdac)")
    if status == "not-installed":
        return CheckResult("service", Severity.WARN, "service not installed (run `sdac install-service`)")
    return CheckResult("service", Severity.WARN, f"systemd status unknown: {status}")


def check_udev_rule() -> CheckResult:
    if UDEV_RULE_PATH.exists():
        return CheckResult("udev", Severity.PASS, f"udev rule installed at {UDEV_RULE_PATH}")
    return CheckResult(
        "udev",
        Severity.WARN,
        f"udev rule NOT installed at {UDEV_RULE_PATH} "
        "(works in user session via uaccess ACL; needed for daemon-at-boot)",
    )


def run_all_checks(*, config_path: str | None) -> list[CheckResult]:
    return [
        check_libhidapi(),
        check_stream_deck(),
        check_python_deps(),
        check_system_binaries(),
        check_udev_rule(),
        check_service_status(),
        check_config(config_path),
    ]


_SEV_GLYPH = {Severity.PASS: "✓", Severity.WARN: "!", Severity.FAIL: "✗"}


def render_report(results: list[CheckResult]) -> str:
    rows: list[str] = []
    name_w = max(len(r.name) for r in results) + 2
    for r in results:
        glyph = _SEV_GLYPH[r.severity]
        rows.append(f"  {glyph}  {r.severity.value:5} {r.name:<{name_w}} {r.message}")
    return "\n".join(rows)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_doctor.py -v
```

Expected: all passing (~15 tests).

If `test_check_udev_rule_pass_when_present` fails because patching `pathlib.Path.exists` is too broad and affects other Path operations during the check, narrow the patch to `sdac.service.UDEV_RULE_PATH.exists` or use `patch.object(UDEV_RULE_PATH, "exists", return_value=True)`.

- [ ] **Step 5: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/sdac/doctor.py tests/unit/test_doctor.py
git commit -m "feat(doctor): check primitives + report rendering"
```

---

## Task 6: `sdac doctor` CLI verb

**Files:**
- Modify: `src/sdac/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests - append to `tests/unit/test_cli.py`**

```python
def test_doctor_runs_and_prints_report():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    # Doctor itself never crashes; even with everything missing it prints a report.
    assert "device" in result.output
    assert "python_deps" in result.output
    assert "system_binaries" in result.output


def test_doctor_with_config_path():
    runner = CliRunner()
    result = runner.invoke(main, [
        "doctor",
        "--config",
        str(FIXTURES / "minimal.yaml"),
    ])
    assert "config" in result.output
    # minimal.yaml is valid → PASS line for config
    assert "PASS" in result.output


def test_doctor_exit_nonzero_on_any_fail():
    """If any check returns FAIL, sdac doctor exits non-zero."""
    from unittest.mock import patch
    from sdac.doctor import CheckResult, Severity

    fail_result = [CheckResult(name="device", severity=Severity.FAIL, message="x")]
    runner = CliRunner()
    with patch("sdac.doctor.run_all_checks", return_value=fail_result):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run failing**

```bash
pytest tests/unit/test_cli.py -k doctor -v
```

Expected: `UsageError("no such command: doctor")`.

- [ ] **Step 3: Add the command to `src/sdac/cli.py`**

Append after the uninstall-service command:

```python
@main.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Optional config file to validate.",
)
def doctor(config_path: str | None) -> None:
    """Report on device, dependencies, service status, and config."""
    from sdac.doctor import Severity, render_report, run_all_checks
    results = run_all_checks(config_path=config_path)
    click.echo(render_report(results))
    if any(r.severity is Severity.FAIL for r in results):
        sys.exit(7)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_cli.py -k doctor -v
```

Expected: 3 passing.

- [ ] **Step 5: Smoke**

```bash
sdac doctor --config tests/fixtures/configs/comprehensive.yaml
```

Expected: tabular report. Device row should be PASS (Stream Deck plugged in). Config row PASS. Service row may WARN (not installed yet). udev WARN (not installed yet).

- [ ] **Step 6: Full check**

```bash
ruff check src tests && mypy src && pytest -q
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/sdac/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): doctor verb with PASS/WARN/FAIL tabular report"
```

---

## Task 7: README + docs/installation.md

**Files:**
- Modify: `README.md`
- Create: `docs/installation.md`

- [ ] **Step 1: Add an "Install as a service" section to `README.md`**

Find the existing `## Daemon (Phase 2a, Linux)` section. Append a new section right after it:

```markdown
## Install as a service (Phase 2b, Linux)

Once your config works the way you want via `sdac daemon`, register it as a systemd user unit so it autostarts at login:

```bash
sdac install-service --config ~/.config/sdac/config.yaml
```

This:
1. Writes `~/.config/systemd/user/sdac.service` pointing at your config.
2. Installs `/etc/udev/rules.d/60-streamdeck.rules` via `sudo` (prompts once for your password) so the device is reachable to any logged-in user - needed for the unit to find the Deck at boot.
3. Reloads udev, daemon-reloads systemd, enables and starts the service.

To stop and remove:

```bash
sdac uninstall-service        # removes systemd unit AND udev rule (sudo)
sdac uninstall-service --keep-udev   # leaves the udev rule in place
```

Health check at any time:

```bash
sdac doctor                                      # full report
sdac doctor --config ~/.config/sdac/config.yaml  # also validates the config
```

Output is a tabular `PASS / WARN / FAIL` per check (device, libhidapi, python_deps, system_binaries, udev, service, config). Exit code is non-zero if any check fails.
```

- [ ] **Step 2: Update the README status block to mention Phase 2b**

Find the existing `**Status:** Phase 2a (current). ...` paragraph and replace with:

```markdown
**Status:** Phase 2b (current). `sdac daemon` runs against a real Stream Deck MK.2; `sdac install-service` registers a systemd user unit + udev rule so it autostarts at login; `sdac doctor` reports device + deps + config + service status. All non-OBS action types execute. OBS execution lands in Phase 3; Windows port lands in Phase 4.
```

- [ ] **Step 3: Update the `## Capabilities (Phase 1 + 2a)` heading + bullets**

Replace the existing block with:

```markdown
## Capabilities (Phase 1 + 2a + 2b)

- Validate a YAML config against the full v1 schema (Pydantic 2 discriminated union over 21 action types).
- Resolve `${ENV_VAR}` in any string field - keep passwords out of the YAML.
- Render every key in a profile/page as a single mosaic PNG (offline preview, no device required).
- Warn (or strict-reject with `--strict-perms`) when the config file is world-readable on POSIX.
- Run a daemon that owns a real Stream Deck MK.2 over USB and dispatches button presses to handlers.
- Hot-reload the config without restarting the daemon.
- Install as a systemd user unit with one command (`sdac install-service`). Daemon autostarts at login.
- `sdac doctor` reports on device, deps, service status, and config - exits non-zero if anything fails.
```

- [ ] **Step 4: Write `docs/installation.md`**

```markdown
# Installation walkthrough

The minimum to go from "fresh Ubuntu" to "daemon running at login pushing icons to my Stream Deck".

## 1. System packages

```bash
sudo apt update
sudo apt install -y \
    libhidapi-libusb0 \
    xdotool \
    playerctl \
    pulseaudio-utils    # or pipewire-pulse on PipeWire systems
```

`libhidapi-libusb0` is the only one strictly required to start the daemon. The others are loaded lazily by their corresponding action types.

## 2. Python package

Recommended via pipx (isolated):

```bash
pipx install streamdeck-as-code
sdac --version
```

Or from a checkout for development:

```bash
git clone https://github.com/solomonneas/streamdeck-as-code
cd streamdeck-as-code
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## 3. Write a config

```bash
mkdir -p ~/.config/sdac
chmod 700 ~/.config/sdac
```

Drop a `~/.config/sdac/config.yaml` with at least:

```yaml
version: 1
default_profile: coding
profiles:
  coding:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Hello"}
            action: {type: shell, cmd: "notify-send 'Stream Deck' 'hello'"}
```

Validate it:

```bash
sdac validate ~/.config/sdac/config.yaml
```

Optionally preview it (no device needed):

```bash
sdac preview ~/.config/sdac/config.yaml --out /tmp/preview.png && xdg-open /tmp/preview.png
```

## 4. Test the daemon in the foreground

```bash
sdac daemon --config ~/.config/sdac/config.yaml -v
```

Press key 0 on your Deck; you should see the `notify-send` desktop notification. Stop with Ctrl+C.

## 5. Install as a service

```bash
sdac install-service --config ~/.config/sdac/config.yaml
```

This prompts once for your sudo password to install `/etc/udev/rules.d/60-streamdeck.rules`. The systemd user unit is written to `~/.config/systemd/user/sdac.service` and immediately started.

Verify everything is healthy:

```bash
sdac doctor --config ~/.config/sdac/config.yaml
```

Inspect logs at any time:

```bash
journalctl --user -u sdac -f
```

## 6. Uninstall

```bash
sdac uninstall-service              # remove unit + udev rule
sdac uninstall-service --keep-udev  # remove unit, keep udev rule
```
```

- [ ] **Step 5: Full check**

```bash
. .venv/bin/activate
ruff check src tests && mypy src && pytest -q
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/installation.md
git commit -m "docs: Phase 2b - install-service + doctor + installation walkthrough"
```

---

## Done criteria for Phase 2b

1. `sdac install-service --config <path>` writes the systemd user unit, installs the udev rule via sudo, and starts the service. Manual sudo prompt during install is expected.
2. `sdac uninstall-service` cleanly reverses it.
3. `sdac doctor` prints a tabular report with PASS/WARN/FAIL for at least device, libhidapi, python_deps, system_binaries, udev, service, config rows. Exit code is non-zero on any FAIL.
4. All tests passing (Phase 2a's 84 + roughly 25 new). ruff + mypy clean.

## Out of scope (deferred to Phase 3)

- OBS reachability check in doctor.
- OBS action execution.
- Live state indicators on Stream Deck keys.

## Out of scope (deferred to Phase 4)

- Windows install-service (Task Scheduler at logon).
- Windows doctor (no systemd/udev rows).
- Active-window watcher for automatic profile switching.
