import sys
from pathlib import Path

import pytest

from deckctl.config import Config, load_config
from deckctl.errors import ConfigError

WINDOWS = sys.platform.startswith("win")

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
    bad.write_text(
        "version: 1\ndefault_profile: ghost\nprofiles:\n  coding:\n    default_page: home\n    "
        "pages:\n      home:\n        keys: {}\n"
    )
    with pytest.raises(ConfigError, match="default_profile"):
        load_config(bad)


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


def test_env_var_substitution(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DECKCTL_TEST_OBS_PASS", "secret-from-env")
    cfg = load_config(FIXTURES / "env_var.yaml")
    assert cfg.obs_hosts["roc"].url == "obsws://127.0.0.1:4455/secret-from-env"


def test_env_var_missing_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DECKCTL_TEST_OBS_PASS", raising=False)
    with pytest.raises(ConfigError, match="DECKCTL_TEST_OBS_PASS"):
        load_config(FIXTURES / "env_var.yaml")


def test_env_var_substitution_in_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DECKCTL_TEST_CMD", "echo hello")
    p = tmp_path / "c.yaml"
    p.write_text(
        "version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
        "pages:\n      p:\n        keys:\n          0:\n            icon: {text: hi}\n"
        "            action: {type: shell, cmd: \"${DECKCTL_TEST_CMD}\"}\n"
    )
    cfg = load_config(p)
    assert cfg.profiles["x"].pages["p"].keys[0].action.cmd == "echo hello"


@pytest.mark.skipif(WINDOWS, reason="POSIX permission semantics only")
def test_strict_perms_rejects_world_readable(tmp_path: Path):
    from deckctl.errors import ConfigPermissionError
    p = tmp_path / "open.yaml"
    p.write_text(
        "version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
        "pages:\n      p:\n        keys: {}\n"
    )
    p.chmod(0o644)
    with pytest.raises(ConfigPermissionError):
        load_config(p, strict_perms=True)


@pytest.mark.skipif(WINDOWS, reason="POSIX permission semantics only")
def test_loose_perms_emit_warning(tmp_path: Path, recwarn):
    p = tmp_path / "open.yaml"
    p.write_text(
        "version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
        "pages:\n      p:\n        keys: {}\n"
    )
    p.chmod(0o644)
    load_config(p)  # warn-only by default
    assert any(
        "0644" in str(w.message) or "permissions" in str(w.message).lower()
        for w in recwarn.list
    )


@pytest.mark.skipif(WINDOWS, reason="POSIX permission semantics only")
def test_strict_perms_passes_on_0600(tmp_path: Path):
    p = tmp_path / "closed.yaml"
    p.write_text(
        "version: 1\ndefault_profile: x\nprofiles:\n  x:\n    default_page: p\n    "
        "pages:\n      p:\n        keys: {}\n"
    )
    p.chmod(0o600)
    load_config(p, strict_perms=True)  # no exception
