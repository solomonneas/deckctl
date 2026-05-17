"""Click CLI entry point. Subcommands are wired here; logic lives in
sibling modules (config, render).
"""

from __future__ import annotations

import sys

import click

from sdac import __version__
from sdac.config import load_config
from sdac.errors import ConfigError
from sdac.render import render_mosaic


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="sdac")
def main() -> None:
    """streamdeck-as-code — declarative Stream Deck driver."""


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--strict-perms",
    is_flag=True,
    help="Reject files with permissions wider than 0600 (POSIX only).",
)
def validate(config_path: str, strict_perms: bool) -> None:
    """Validate a config file."""
    try:
        cfg = load_config(config_path, strict_perms=strict_perms)
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    n_profiles = len(cfg.profiles)
    n_keys = sum(
        len(page.keys)
        for p in cfg.profiles.values()
        for page in p.pages.values()
    )
    click.echo(f"OK: {config_path} ({n_profiles} profile(s), {n_keys} key(s) configured)")


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--out", type=click.Path(dir_okay=False, writable=True), default="preview.png")
@click.option("--profile", default=None, help="Profile name to preview. Defaults to default_profile.")
@click.option("--page", default=None, help="Page name to preview. Defaults to the profile's default_page.")
def preview(config_path: str, out: str, profile: str | None, page: str | None) -> None:
    """Render a profile/page as a mosaic PNG."""
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    pname = profile or cfg.default_profile
    if pname not in cfg.profiles:
        click.echo(f"unknown profile: {pname}", err=True)
        sys.exit(3)
    p = cfg.profiles[pname]
    page_name = page or p.default_page
    if page_name not in p.pages:
        click.echo(f"unknown page: {page_name} in profile {pname}", err=True)
        sys.exit(4)
    img = render_mosaic(p.pages[page_name])
    img.save(out)
    click.echo(f"Wrote {out} ({img.width}x{img.height})")
