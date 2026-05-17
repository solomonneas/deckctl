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


_PY_DEPS = ["StreamDeck", "watchdog", "pydantic", "click", "PIL", "pilmoji", "yaml"]


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


_SEV_LABEL = {
    Severity.PASS: "[ OK ]",
    Severity.WARN: "[WARN]",
    Severity.FAIL: "[FAIL]",
}


def render_report(results: list[CheckResult]) -> str:
    rows: list[str] = []
    name_w = max(len(r.name) for r in results) + 2
    for r in results:
        label = _SEV_LABEL[r.severity]
        rows.append(f"  {label}  {r.severity.value:5} {r.name:<{name_w}} {r.message}")
    return "\n".join(rows)
