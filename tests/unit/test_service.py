from __future__ import annotations

import sys
from pathlib import Path

import pytest

WINDOWS = sys.platform.startswith("win")
pytestmark = pytest.mark.skipif(WINDOWS, reason="systemd is Linux-only")

from deckctl.service import (  # noqa: E402
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
        deckctl_path="/home/user/.local/bin/deckctl",
        config_path="/home/user/.config/deckctl/config.yaml",
    )
    assert "/home/user/.local/bin/deckctl daemon" in rendered
    assert "--config /home/user/.config/deckctl/config.yaml" in rendered
    assert "{deckctl_path}" not in rendered
    assert "{config_path}" not in rendered
    assert "[Service]" in rendered
    assert "Restart=on-failure" in rendered


def test_udev_rule_name_constant():
    assert UDEV_RULE_NAME == "60-streamdeck.rules"
