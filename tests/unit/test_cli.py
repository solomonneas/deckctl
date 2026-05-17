from click.testing import CliRunner

from sdac import __version__
from sdac.cli import main


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
