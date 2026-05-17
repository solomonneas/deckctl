"""Click CLI entry point. Subcommands are wired here; logic lives in
sibling modules (config, render).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

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


@main.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Path to the YAML config file.",
)
@click.option(
    "--mock",
    is_flag=True,
    help="Use an in-memory MockDevice instead of real hardware (dev / CI).",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def daemon(config_path: str, mock: bool, verbose: bool) -> None:
    """Run the Stream Deck daemon (foreground)."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from sdac.device import Device
    device: Device
    if mock:
        from sdac.device import MockDevice
        device = MockDevice()
    else:
        from sdac.device import DeviceNotFoundError, StreamDeckDevice
        try:
            device = StreamDeckDevice.enumerate_first()
        except DeviceNotFoundError as e:
            click.echo(str(e), err=True)
            sys.exit(5)
    from sdac.daemon import Daemon
    d = Daemon(device=device, config_path=config_path)
    try:
        d.load()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    click.echo(f"starting daemon: {config_path} (mock={mock})")
    d.render_current_page()
    d.start_watching()
    d.run_forever()
    click.echo("daemon stopped")


@main.command("install-service")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Path to the YAML config file. Stored absolutely in the unit.",
)
@click.option(
    "--sdac-path",
    default=None,
    help="Override the path to the `sdac` binary embedded in the unit. Defaults to `which sdac`.",
)
def install_service(config_path: str, sdac_path: str | None) -> None:
    """Install + enable + start the systemd user unit (and udev rule via sudo)."""
    import logging
    import shutil
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from sdac.service import ServiceError
    from sdac.service import install_service as _install
    resolved_sdac = sdac_path or shutil.which("sdac") or "sdac"
    abs_config = str(Path(config_path).resolve())
    try:
        _install(sdac_path=resolved_sdac, config_path=abs_config)
    except ServiceError as e:
        click.echo(str(e), err=True)
        sys.exit(6)
    click.echo(f"installed: systemd unit + udev rule; service active with --config {abs_config}")
