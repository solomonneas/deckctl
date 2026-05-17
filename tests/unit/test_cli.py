from pathlib import Path

from click.testing import CliRunner

from sdac import __version__
from sdac.cli import main

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
    with patch("sdac.daemon.Daemon.run_forever", return_value=None):
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
    with patch("sdac.service.install_service") as inst:
        result = runner.invoke(main, ["install-service", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    inst.assert_called_once()
    kwargs = inst.call_args.kwargs
    assert kwargs["config_path"] == str(cfg.resolve())
    assert kwargs["sdac_path"].endswith("/sdac") or kwargs["sdac_path"] == "sdac"


def test_install_service_errors_when_config_missing(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["install-service", "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0


def test_uninstall_service_invokes_uninstall():
    from unittest.mock import patch
    runner = CliRunner()
    with patch("sdac.service.uninstall_service") as un:
        result = runner.invoke(main, ["uninstall-service"])
    assert result.exit_code == 0, result.output
    un.assert_called_once_with(remove_udev=True)


def test_uninstall_service_keep_udev_flag():
    from unittest.mock import patch
    runner = CliRunner()
    with patch("sdac.service.uninstall_service") as un:
        result = runner.invoke(main, ["uninstall-service", "--keep-udev"])
    assert result.exit_code == 0, result.output
    un.assert_called_once_with(remove_udev=False)
