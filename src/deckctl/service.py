"""systemd-user-unit + udev-rule install lifecycle.

Linux-only. The CLI verbs `install-service` / `uninstall-service` are thin
wrappers around install_service() / uninstall_service() below.

This module is the *only* place we shell to `sudo`. Everywhere else uses the
device or daemon abstractions.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from deckctl.errors import SdacError

log = logging.getLogger(__name__)

SERVICE_NAME = "deckctl.service"
UDEV_RULE_NAME = "60-streamdeck.rules"
UDEV_RULE_PATH = Path("/etc/udev/rules.d") / UDEV_RULE_NAME


class ServiceError(SdacError):
    """Raised when service install / uninstall fails."""


def user_unit_path() -> Path:
    """Path to the systemd user unit for the current user.

    On Windows this returns a path under `~/.config/systemd/user/` for
    consistency, even though Windows doesn't run systemd. Callers that
    actually install the unit gate on `sys.platform` separately.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "systemd" / "user" / SERVICE_NAME


def render_systemd_unit(*, deckctl_path: str, config_path: str) -> str:
    """Substitute the systemd unit template with absolute paths."""
    tpl = files("deckctl.assets.systemd").joinpath("deckctl.service.template").read_text()
    return tpl.format(deckctl_path=deckctl_path, config_path=config_path)


def udev_rule_text() -> str:
    """The packaged udev rule, verbatim."""
    return files("deckctl.assets.udev").joinpath(UDEV_RULE_NAME).read_text()


def write_user_unit(deckctl_path: str, config_path: str) -> Path:
    """Write the substituted unit to ~/.config/systemd/user/deckctl.service."""
    dest = user_unit_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_systemd_unit(deckctl_path=deckctl_path, config_path=config_path))
    log.info("wrote %s", dest)
    return dest


def install_udev_rule_with_sudo() -> None:
    """Copy the packaged udev rule to /etc/udev/rules.d via sudo, then reload udev.

    Will prompt the user for their sudo password if not cached.
    """
    text = udev_rule_text()
    stage = Path("/tmp/deckctl-60-streamdeck.rules")
    stage.write_text(text)
    try:
        subprocess.run(["sudo", "cp", str(stage), str(UDEV_RULE_PATH)], check=True)
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["sudo", "udevadm", "trigger"], check=True)
        log.info("udev rule installed at %s", UDEV_RULE_PATH)
    except subprocess.CalledProcessError as e:
        raise ServiceError(f"udev install failed: {e}") from e
    finally:
        with contextlib.suppress(FileNotFoundError):
            stage.unlink()


def systemctl_user(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a `systemctl --user ...` command and capture output."""
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def install_service(*, deckctl_path: str, config_path: str) -> None:
    """Full install: write unit, install udev rule, daemon-reload, enable+start."""
    if sys.platform.startswith("win"):
        raise ServiceError("install-service is Linux-only (Windows ships in Phase 4)")
    if not shutil.which("systemctl"):
        raise ServiceError("systemctl not found; this machine doesn't run systemd")
    write_user_unit(deckctl_path=deckctl_path, config_path=config_path)
    install_udev_rule_with_sudo()
    systemctl_user("daemon-reload")
    systemctl_user("enable", "--now", SERVICE_NAME)
    log.info("service installed and started")


def uninstall_service(*, remove_udev: bool = True) -> None:
    """Stop + disable + remove the user unit. Optionally remove the udev rule via sudo."""
    if sys.platform.startswith("win"):
        raise ServiceError("uninstall-service is Linux-only")
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
