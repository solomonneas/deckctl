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
