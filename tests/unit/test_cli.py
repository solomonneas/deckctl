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
