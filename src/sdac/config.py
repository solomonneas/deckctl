"""Config schema (Pydantic v2) and YAML loader.

Single place YAML is parsed and validated. Discriminated union over the
`type` field powers the action grammar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sdac.errors import ConfigError

MK2_KEY_COUNT = 15  # 5x3 grid


# ---------- Icons ----------


class IconSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = None
    emoji: str | None = None
    image: str | None = None  # path relative to config file
    bg: str | None = None  # hex color, idle (default)
    bg_idle: str | None = None  # alias for bg; takes precedence when set
    bg_active: str | None = None
    bg_pressed: str | None = None
    bg_error: str | None = None
    bg_disconnected: str | None = None
    fg: str | None = "#ffffff"

    @model_validator(mode="after")
    def _must_have_visible_content(self) -> IconSpec:
        if not any([self.text, self.emoji, self.image]):
            raise ValueError("icon must have at least one of: text, emoji, image")
        return self


class Indicator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bind: Literal[
        "obs.recording.state",
        "obs.streaming.state",
        "obs.replay.state",
        "obs.virtualcam.state",
        "obs.scene.current",
        "obs.input.muted",
    ]
    host: str
    scene: str | None = None  # used with obs.scene.current
    input_name: str | None = None  # used with obs.input.muted


# ---------- Actions (discriminated union on `type`) ----------


class _ActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShellAction(_ActionBase):
    type: Literal["shell"]
    cmd: str
    cwd: str | None = None
    shell: str | None = None


class KeyChordAction(_ActionBase):
    type: Literal["key.chord"]
    keys: str


class KeyTextAction(_ActionBase):
    type: Literal["key.text"]
    text: str


class OpenUrlAction(_ActionBase):
    type: Literal["open.url"]
    url: str


class OpenAppAction(_ActionBase):
    type: Literal["open.app"]
    path: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> OpenAppAction:
        if not (bool(self.path) ^ bool(self.name)):
            raise ValueError("open.app requires exactly one of path or name")
        return self


class ObsSceneSwitchAction(_ActionBase):
    type: Literal["obs.scene.switch"]
    host: str
    scene: str


class ObsRecordingToggleAction(_ActionBase):
    type: Literal["obs.recording.toggle"]
    host: str


class ObsStreamingToggleAction(_ActionBase):
    type: Literal["obs.streaming.toggle"]
    host: str


class ObsReplaySaveAction(_ActionBase):
    type: Literal["obs.replay.save"]
    host: str


class ObsVirtualCamToggleAction(_ActionBase):
    type: Literal["obs.virtualcam.toggle"]
    host: str


class ObsInputMuteToggleAction(_ActionBase):
    type: Literal["obs.input.mute.toggle"]
    host: str
    input_name: str


class SystemVolumeUpAction(_ActionBase):
    type: Literal["system.volume.up"]
    step: int = 5


class SystemVolumeDownAction(_ActionBase):
    type: Literal["system.volume.down"]
    step: int = 5


class SystemVolumeMuteAction(_ActionBase):
    type: Literal["system.volume.mute"]


class MediaPlayAction(_ActionBase):
    type: Literal["media.play"]


class MediaPauseAction(_ActionBase):
    type: Literal["media.pause"]


class MediaNextAction(_ActionBase):
    type: Literal["media.next"]


class MediaPrevAction(_ActionBase):
    type: Literal["media.prev"]


class PageGoAction(_ActionBase):
    type: Literal["page.go"]
    page: str


class ProfileSwitchAction(_ActionBase):
    type: Literal["profile.switch"]
    profile: str


class CompoundAction(_ActionBase):
    type: Literal["compound"]
    actions: list[Action]
    continue_on_error: bool = False


Action = Annotated[
    ShellAction
    | KeyChordAction
    | KeyTextAction
    | OpenUrlAction
    | OpenAppAction
    | ObsSceneSwitchAction
    | ObsRecordingToggleAction
    | ObsStreamingToggleAction
    | ObsReplaySaveAction
    | ObsVirtualCamToggleAction
    | ObsInputMuteToggleAction
    | SystemVolumeUpAction
    | SystemVolumeDownAction
    | SystemVolumeMuteAction
    | MediaPlayAction
    | MediaPauseAction
    | MediaNextAction
    | MediaPrevAction
    | PageGoAction
    | ProfileSwitchAction
    | CompoundAction,
    Field(discriminator="type"),
]

# Forward-ref fix for CompoundAction.actions
CompoundAction.model_rebuild()


# ---------- Keys / Pages / Profiles ----------


class KeyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    icon: IconSpec
    action: Action
    indicator: Indicator | None = None


class PageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keys: dict[int, KeyConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _key_indices_in_range(self) -> PageConfig:
        for k in self.keys:
            if not 0 <= k < MK2_KEY_COUNT:
                raise ValueError(
                    f"key index {k} out of range; Stream Deck MK.2 supports 0..{MK2_KEY_COUNT - 1}"
                )
        return self


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


# ---------- Top-level ----------


class ObsHost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str  # obsws://host:port/password (password may be ${ENV_VAR})


class ProfileRuleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_class: list[str] = Field(default_factory=list)  # Linux WM_CLASS
    app_name: list[str] = Field(default_factory=list)  # Windows process name


class ProfileRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str
    when: ProfileRuleWhen


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    vars: dict[str, str] = Field(default_factory=dict)
    obs_hosts: dict[str, ObsHost] = Field(default_factory=dict)
    profile_rules: list[ProfileRule] = Field(default_factory=list)
    default_profile: str
    profiles: dict[str, ProfileConfig]

    @model_validator(mode="after")
    def _validate_top_level(self) -> Config:
        if self.version != 1:
            raise ValueError(f"unsupported schema version: {self.version} (only 1 is supported)")
        if self.default_profile not in self.profiles:
            raise ValueError(
                f"default_profile '{self.default_profile}' not in profiles {list(self.profiles)}"
            )
        # page.go targets must exist within their own profile;
        # profile.switch targets must reference an existing profile.
        for pname, profile in self.profiles.items():
            for page_name, page in profile.pages.items():
                for kidx, k in page.keys.items():
                    if isinstance(k.action, PageGoAction) and k.action.page not in profile.pages:
                        raise ValueError(
                            f"profile {pname!r}, page {page_name!r}, key {kidx}: "
                            f"page.go target '{k.action.page}' not found in profile"
                        )
                    if (
                        isinstance(k.action, ProfileSwitchAction)
                        and k.action.profile not in self.profiles
                    ):
                        raise ValueError(
                            f"profile {pname!r}, page {page_name!r}, key {kidx}: "
                            f"profile.switch target '{k.action.profile}' not found"
                        )
        return self


# ---------- Loader ----------


def load_config(path: str | Path) -> Config:
    """Parse and validate a YAML config file. Raises ConfigError on any failure."""
    p = Path(path)
    try:
        raw: Any = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: top-level YAML must be a mapping")
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"{p}: schema validation failed:\n{e}") from e
