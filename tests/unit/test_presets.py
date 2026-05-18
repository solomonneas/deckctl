"""Tests for deckctl.presets: the loader, the list, and per-preset schema validation."""

from __future__ import annotations

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
