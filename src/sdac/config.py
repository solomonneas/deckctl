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
    def _default_page_exists(self) -> ProfileConfig:
        if self.default_page not in self.pages:
            raise ValueError(
                f"default_page '{self.default_page}' not in pages {list(self.pages)}"
            )
        return self


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(..., description="Schema version; only 1 is supported.")
    vars: dict[str, str] = Field(default_factory=dict)
    default_profile: str
    profiles: dict[str, ProfileConfig]

    @model_validator(mode="after")
    def _validate_top_level(self) -> Config:
        if self.version != 1:
            raise ValueError(
                f"unsupported schema version: {self.version} (only 1 is supported)"
            )
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
