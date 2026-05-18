"""Bundled YAML presets accessible via `deckctl init <name>`.

Each preset is a complete config file shipped as package data. The CLI's
`init` command reads one via `get_preset()` and writes it to the user's
config path.

Adding a new preset:
1. Drop the YAML file next to this module (e.g. `myproject.yaml`).
2. Add an entry to DESCRIPTIONS below.
3. The parameterized schema-validation test in tests/unit/test_presets.py
   picks it up automatically and fails the build if the YAML doesn't validate.
"""

from __future__ import annotations

from importlib.resources import files

DESCRIPTIONS: dict[str, str] = {
    "default": "Minimal 3-key smoke layout. Use after install to verify everything works.",
}


def list_presets() -> dict[str, str]:
    """Return the available presets as {name: one-line-description}."""
    return DESCRIPTIONS


def get_preset(name: str) -> str:
    """Return the raw YAML text for the named preset.

    Raises KeyError if the preset is not in DESCRIPTIONS.
    """
    if name not in DESCRIPTIONS:
        raise KeyError(f"unknown preset {name!r} (available: {sorted(DESCRIPTIONS)})")
    return files("deckctl.presets").joinpath(f"{name}.yaml").read_text()
