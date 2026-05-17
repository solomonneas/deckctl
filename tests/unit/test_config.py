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
    bad.write_text(
        "version: 1\ndefault_profile: ghost\nprofiles:\n  coding:\n    default_page: home\n    "
        "pages:\n      home:\n        keys: {}\n"
    )
    with pytest.raises(ConfigError, match="default_profile"):
        load_config(bad)
