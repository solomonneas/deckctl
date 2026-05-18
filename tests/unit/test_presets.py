"""Tests for deckctl.presets: the loader, the list, and per-preset schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from deckctl.presets import DESCRIPTIONS, get_preset, list_presets


def test_list_presets_returns_dict_of_name_to_description():
    presets = list_presets()
    assert isinstance(presets, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in presets.items())


def test_descriptions_dict_is_the_source_of_truth():
    """list_presets() should return DESCRIPTIONS as-is."""
    assert list_presets() == DESCRIPTIONS


def test_get_preset_unknown_name_raises_key_error():
    with pytest.raises(KeyError, match="unknown preset"):
        get_preset("nonexistent")


@pytest.mark.parametrize("name", list(DESCRIPTIONS))
def test_bundled_preset_validates_against_schema(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every bundled preset must load cleanly through the production schema."""
    # Streaming presets reference ${DECKCTL_OBS_LOCAL_PASS}; set a dummy value
    # so env-var substitution succeeds. (Schema doesn't care about the value.)
    monkeypatch.setenv("DECKCTL_OBS_LOCAL_PASS", "test-password-not-used")

    from deckctl.config import load_config

    raw = get_preset(name)
    p = tmp_path / f"{name}.yaml"
    p.write_text(raw)

    cfg = load_config(p)
    assert cfg.version == 1
    assert cfg.default_profile in cfg.profiles


def test_get_preset_returns_text_for_known_name():
    """Sanity check the loader actually returns YAML content."""
    text = get_preset("default")
    assert "version: 1" in text
    assert "profiles:" in text
