from __future__ import annotations

import sdac.actions  # noqa: F401
from sdac.actions import get_handler
from sdac.config import PageGoAction, ProfileSwitchAction


class _RecordingCtx:
    def __init__(self) -> None:
        self.pages: list[str] = []
        self.profiles: list[str] = []

    def switch_page(self, name: str) -> None:
        self.pages.append(name)

    def switch_profile(self, name: str) -> None:
        self.profiles.append(name)

    def obs_host_url(self, name: str) -> str:
        raise KeyError(f"unknown obs host: {name}")


def test_page_go_calls_ctx_switch_page():
    ctx = _RecordingCtx()
    action = PageGoAction(type="page.go", page="git")
    get_handler("page.go").execute(action, ctx)
    assert ctx.pages == ["git"]
    assert ctx.profiles == []


def test_profile_switch_calls_ctx_switch_profile():
    ctx = _RecordingCtx()
    action = ProfileSwitchAction(type="profile.switch", profile="streaming")
    get_handler("profile.switch").execute(action, ctx)
    assert ctx.profiles == ["streaming"]
    assert ctx.pages == []
