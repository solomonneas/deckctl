from pathlib import Path

from click.testing import CliRunner

from deckctl import __version__
from deckctl.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


def test_cli_version_prints_package_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0, result.output
    assert __version__ in result.output


def test_cli_help_lists_validate_and_preview():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.output
    assert "preview" in result.output


def test_validate_minimal_succeeds():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "minimal.yaml")])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_invalid_exits_nonzero_with_error():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "invalid_schema.yaml")])
    assert result.exit_code != 0
    assert "default_profile" in result.output


def test_validate_comprehensive_succeeds():
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(FIXTURES / "comprehensive.yaml")])
    assert result.exit_code == 0, result.output


def test_preview_writes_png(tmp_path: Path):
    out = tmp_path / "preview.png"
    runner = CliRunner()
    result = runner.invoke(main, [
        "preview", str(FIXTURES / "comprehensive.yaml"),
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.stat().st_size > 1024  # at least a kilobyte of PNG


def test_preview_respects_profile_and_page(tmp_path: Path):
    out = tmp_path / "stream.png"
    runner = CliRunner()
    result = runner.invoke(main, [
        "preview", str(FIXTURES / "comprehensive.yaml"),
        "--profile", "streaming",
        "--page", "home",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_preview_unknown_profile_errors(tmp_path: Path):
    out = tmp_path / "x.png"
    runner = CliRunner()
    result = runner.invoke(main, [
        "preview", str(FIXTURES / "comprehensive.yaml"),
        "--profile", "ghost",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert "ghost" in result.output


def test_daemon_command_uses_mock_device_when_flag_set(tmp_path: Path):
    """The --mock flag is for development/CI. With it, daemon uses MockDevice
    and exits immediately (because we patch run_forever)."""
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\nprofiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    runner = CliRunner()
    from unittest.mock import patch
    with patch("deckctl.daemon.Daemon.run_forever", return_value=None):
        result = runner.invoke(main, ["daemon", "--config", str(cfg), "--mock"])
    assert result.exit_code == 0, result.output
    assert "starting" in result.output.lower()


def test_daemon_command_unknown_config_errors(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["daemon", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code != 0


def test_install_service_calls_install_with_resolved_paths(tmp_path: Path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "version: 1\ndefault_profile: a\nprofiles:\n  a:\n    default_page: home\n"
        "    pages:\n      home:\n        keys: {}\n"
    )
    from unittest.mock import patch
    runner = CliRunner()
    with patch("deckctl.service.install_service") as inst:
        result = runner.invoke(main, ["install-service", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    inst.assert_called_once()
    kwargs = inst.call_args.kwargs
    assert kwargs["config_path"] == str(cfg.resolve())
    assert "deckctl" in kwargs["deckctl_path"].lower()


def test_install_service_errors_when_config_missing(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["install-service", "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0


def test_uninstall_service_invokes_uninstall():
    from unittest.mock import patch
    runner = CliRunner()
    with patch("deckctl.service.uninstall_service") as un:
        result = runner.invoke(main, ["uninstall-service"])
    assert result.exit_code == 0, result.output
    un.assert_called_once_with(remove_udev=True)


def test_uninstall_service_keep_udev_flag():
    from unittest.mock import patch
    runner = CliRunner()
    with patch("deckctl.service.uninstall_service") as un:
        result = runner.invoke(main, ["uninstall-service", "--keep-udev"])
    assert result.exit_code == 0, result.output
    un.assert_called_once_with(remove_udev=False)


def test_doctor_runs_and_prints_report():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    # Doctor itself never crashes; even with everything missing it prints a report.
    assert "device" in result.output
    assert "python_deps" in result.output
    assert "system_binaries" in result.output


def test_doctor_with_config_path():
    runner = CliRunner()
    result = runner.invoke(main, [
        "doctor",
        "--config",
        str(FIXTURES / "minimal.yaml"),
    ])
    assert "config" in result.output
    # minimal.yaml is valid → PASS line for config
    assert "PASS" in result.output


def test_doctor_exit_nonzero_on_any_fail():
    """If any check returns FAIL, deckctl doctor exits non-zero."""
    from unittest.mock import patch

    from deckctl.doctor import CheckResult, Severity

    fail_result = [CheckResult(name="device", severity=Severity.FAIL, message="x")]
    runner = CliRunner()
    with patch("deckctl.doctor.run_all_checks", return_value=fail_result):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code != 0


def test_init_list_prints_available_presets():
    runner = CliRunner()
    result = runner.invoke(main, ["init", "--list"])
    assert result.exit_code == 0, result.output
    assert "default" in result.output
    assert "coding" in result.output
    assert "streaming-twitch" in result.output
    assert "streaming-youtube" in result.output


def test_init_unknown_name_errors():
    runner = CliRunner()
    result = runner.invoke(main, ["init", "nonexistent"])
    assert result.exit_code == 1
    assert "unknown preset" in result.output.lower()


def test_init_writes_default_preset_to_chosen_path(tmp_path: Path):
    out = tmp_path / "config.yaml"
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "version: 1" in text
    assert "default_profile: default" in text


def test_init_refuses_to_overwrite_existing_without_force(tmp_path: Path):
    out = tmp_path / "config.yaml"
    out.write_text("# existing config\n")
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out)])
    assert result.exit_code == 2
    assert "already exists" in result.output.lower()
    assert out.read_text(encoding="utf-8") == "# existing config\n"  # unchanged


def test_init_force_overwrites(tmp_path: Path):
    out = tmp_path / "config.yaml"
    out.write_text("# existing\n")
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out), "--force"])
    assert result.exit_code == 0, result.output
    assert "version: 1" in out.read_text(encoding="utf-8")


def test_init_no_args_shows_usage_with_preset_list():
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code != 0
    assert "coding" in result.output or "default" in result.output


def test_init_default_path_honors_xdg_config_home(tmp_path: Path, monkeypatch):
    """XDG_CONFIG_HOME wins over ~/.config/. Matches sdac.service convention."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default"])
    assert result.exit_code == 0, result.output
    expected = tmp_path / "xdg" / "deckctl" / "config.yaml"
    assert expected.exists()
    assert "version: 1" in expected.read_text(encoding="utf-8")


def test_init_default_path_falls_back_to_home_dot_config(tmp_path: Path, monkeypatch):
    """When XDG_CONFIG_HOME is unset, write to ~/.config/deckctl/config.yaml."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default"])
    assert result.exit_code == 0, result.output
    expected = tmp_path / "home" / ".config" / "deckctl" / "config.yaml"
    assert expected.exists()


def test_init_atomic_create_no_force_uses_exclusive_open(tmp_path: Path):
    """Even if the destination appears after the (now-removed) exists()-check,
    `open("x")` raises FileExistsError so the user's file is not clobbered.
    """
    out = tmp_path / "config.yaml"
    out.write_text("# my hand-written config\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["init", "default", "--to", str(out)])
    assert result.exit_code == 2
    assert out.read_text(encoding="utf-8") == "# my hand-written config\n"
