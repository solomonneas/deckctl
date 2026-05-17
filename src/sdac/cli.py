"""Click CLI entry point. Subcommands are wired here; logic lives in
sibling modules (config, render).
"""

from __future__ import annotations

import click

from sdac import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="sdac")
def main() -> None:
    """streamdeck-as-code — declarative Stream Deck driver."""


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
def validate(config_path: str) -> None:
    """Validate a config file. Implemented in Task 8."""
    raise click.UsageError("not implemented yet (Task 8)")


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--out", type=click.Path(dir_okay=False, writable=True), default="preview.png")
@click.option("--profile", default=None, help="Profile name to preview. Defaults to default_profile.")
@click.option("--page", default=None, help="Page name to preview. Defaults to the profile's default_page.")
def preview(config_path: str, out: str, profile: str | None, page: str | None) -> None:
    """Render a profile/page as a mosaic PNG. Implemented in Task 13."""
    raise click.UsageError("not implemented yet (Task 13)")
