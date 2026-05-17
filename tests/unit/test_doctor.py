from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sdac.doctor import (
    CheckResult,
    Severity,
    check_config,
    check_libhidapi,
    check_python_deps,
    check_service_status,
    check_stream_deck,
    check_system_binaries,
    check_udev_rule,
    render_report,
    run_all_checks,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_check_result_dataclass():
    r = CheckResult(name="test", severity=Severity.PASS, message="ok")
    assert r.name == "test"
    assert r.severity is Severity.PASS


def test_check_stream_deck_passes_when_device_present():
    class _FakeDev:
        @property
        def key_count(self) -> int:
            return 15
    with patch("sdac.doctor._enumerate_first", return_value=_FakeDev()):
        r = check_stream_deck()
    assert r.severity is Severity.PASS
    assert "found" in r.message.lower()


def test_check_stream_deck_fails_when_not_found():
    with patch("sdac.doctor._enumerate_first", return_value=None):
        r = check_stream_deck()
    assert r.severity is Severity.FAIL


def test_check_stream_deck_fails_on_probe_error():
    with patch("sdac.doctor._enumerate_first", side_effect=RuntimeError("no HID backend")):
        r = check_stream_deck()
    assert r.severity is Severity.FAIL
    assert "no HID backend" in r.message


def test_check_python_deps_passes_when_all_importable():
    r = check_python_deps()
    assert r.severity is Severity.PASS


def test_check_libhidapi_returns_a_result():
    r = check_libhidapi()
    assert r.severity in (Severity.PASS, Severity.FAIL)


def test_check_system_binaries_reports_each():
    r = check_system_binaries()
    assert "xdotool" in r.message
    assert "pactl" in r.message
    assert "playerctl" in r.message


def test_check_config_pass_on_valid():
    r = check_config(str(FIXTURES / "minimal.yaml"))
    assert r.severity is Severity.PASS


def test_check_config_fail_on_invalid():
    r = check_config(str(FIXTURES / "invalid_schema.yaml"))
    assert r.severity is Severity.FAIL


def test_check_config_warn_when_no_path_provided():
    r = check_config(None)
    assert r.severity is Severity.WARN
    assert "skip" in r.message.lower() or "no config" in r.message.lower()


def test_check_service_status_returns_status_severity():
    with patch("sdac.doctor.service_status", return_value="active"):
        r = check_service_status()
    assert r.severity is Severity.PASS

    with patch("sdac.doctor.service_status", return_value="inactive"):
        r = check_service_status()
    assert r.severity is Severity.WARN

    with patch("sdac.doctor.service_status", return_value="failed"):
        r = check_service_status()
    assert r.severity is Severity.FAIL

    with patch("sdac.doctor.service_status", return_value="not-installed"):
        r = check_service_status()
    assert r.severity is Severity.WARN


def test_check_udev_rule_pass_when_present(tmp_path: Path):
    fake_path = tmp_path / "rule.rules"
    fake_path.write_text("dummy")
    with patch("sdac.doctor.UDEV_RULE_PATH", fake_path):
        r = check_udev_rule()
    assert r.severity is Severity.PASS


def test_check_udev_rule_warn_when_absent(tmp_path: Path):
    fake_path = tmp_path / "missing.rules"
    with patch("sdac.doctor.UDEV_RULE_PATH", fake_path):
        r = check_udev_rule()
    assert r.severity is Severity.WARN


def test_render_report_includes_each_check():
    results = [
        CheckResult(name="device", severity=Severity.PASS, message="ok"),
        CheckResult(name="config", severity=Severity.FAIL, message="oops"),
    ]
    out = render_report(results)
    assert "device" in out
    assert "config" in out
    assert "PASS" in out
    assert "FAIL" in out


def test_run_all_checks_returns_list_of_results():
    results = run_all_checks(config_path=None)
    assert isinstance(results, list)
    assert all(isinstance(r, CheckResult) for r in results)
    assert len(results) >= 5


def test_check_obs_reachability_warn_without_config():
    from sdac.doctor import check_obs_reachability
    r = check_obs_reachability(None)
    assert r.severity is Severity.WARN


def test_check_obs_reachability_no_hosts_in_config_passes(tmp_path):
    from sdac.doctor import check_obs_reachability
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\nprofiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    r = check_obs_reachability(str(cfg))
    assert r.severity is Severity.PASS
    assert "no obs_hosts" in r.message.lower()


def test_check_obs_reachability_warn_on_unreachable(tmp_path, monkeypatch):
    from sdac.doctor import check_obs_reachability
    monkeypatch.setenv("SDAC_TEST_OBS_PASS", "x")
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\n"
        "obs_hosts:\n"
        "  ghost:\n    url: obsws://127.0.0.1:6666/${SDAC_TEST_OBS_PASS}\n"
        "profiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    r = check_obs_reachability(str(cfg))
    assert r.severity is Severity.WARN
    assert "ghost" in r.message
