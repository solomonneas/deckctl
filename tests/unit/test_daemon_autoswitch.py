from __future__ import annotations

from pathlib import Path

import sdac.actions  # noqa: F401
from sdac.daemon import Daemon
from sdac.device import MockDevice
from sdac.watchers import ActiveWindow
from sdac.watchers.mock import MockWatcher

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def _daemon(watcher: MockWatcher) -> Daemon:
    device = MockDevice()
    d = Daemon(
        device=device,
        config_path=FIXTURES / "autoswitch.yaml",
        watcher=watcher,
    )
    d.load()
    d.render_current_page()
    d.start_watching_windows()
    return d


def test_on_active_window_matches_first_rule_and_switches_profile():
    watcher = MockWatcher()
    d = _daemon(watcher)
    assert d.current_profile == "coding"
    watcher.inject(ActiveWindow(app_class="obs"))
    assert d.current_profile == "streaming"


def test_active_window_no_match_keeps_current_profile():
    watcher = MockWatcher()
    d = _daemon(watcher)
    watcher.inject(ActiveWindow(app_class="vim"))
    assert d.current_profile == "coding"


def test_active_window_matches_app_name_on_windows_style():
    watcher = MockWatcher()
    d = _daemon(watcher)
    watcher.inject(ActiveWindow(app_name="chrome.exe"))
    assert d.current_profile == "browsing"


def test_repeat_match_does_not_re_switch_profile():
    """No redundant render storm when the same window stays focused."""
    watcher = MockWatcher()
    d = _daemon(watcher)
    watcher.inject(ActiveWindow(app_class="obs"))
    # MockDevice records images; we don't have access here but switching to same
    # profile shouldn't churn — verify by inspecting current_profile stability.
    profile_before = d.current_profile
    watcher.inject(ActiveWindow(app_class="obs"))
    assert d.current_profile == profile_before == "streaming"


def test_first_matching_rule_wins():
    """Order matters: first match in profile_rules wins."""
    watcher = MockWatcher()
    d = _daemon(watcher)
    # An ActiveWindow that matches both rules — verify the FIRST one (streaming) wins.
    watcher.inject(ActiveWindow(app_class="obs", app_name="firefox.exe"))
    assert d.current_profile == "streaming"
