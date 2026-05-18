"""Click CLI entry point. Subcommands are wired here; logic lives in
sibling modules (config, render).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from deckctl import __version__
from deckctl.config import load_config
from deckctl.errors import ConfigError
from deckctl.render import render_mosaic


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="deckctl")
def main() -> None:
    """deckctl — declarative Stream Deck driver."""


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
    from deckctl.device import Device
    device: Device
    if mock:
        from deckctl.device import MockDevice
        device = MockDevice()
    else:
        from deckctl.device import DeviceNotFoundError, StreamDeckDevice
        try:
            device = StreamDeckDevice.enumerate_first()
        except DeviceNotFoundError as e:
            click.echo(str(e), err=True)
            sys.exit(5)
    from deckctl.daemon import Daemon
    from deckctl.watchers import make_watcher
    d = Daemon(device=device, config_path=config_path, watcher=make_watcher())
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
    "--deckctl-path",
    default=None,
    help="Override the path to the `deckctl` binary embedded in the unit. Defaults to `which deckctl`.",
)
def install_service(config_path: str, deckctl_path: str | None) -> None:
    """Install + enable + start the systemd user unit (and udev rule via sudo)."""
    import logging
    import shutil
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from deckctl.service import ServiceError
    from deckctl.service import install_service as _install
    resolved_deckctl = deckctl_path or shutil.which("deckctl") or "deckctl"
    abs_config = str(Path(config_path).resolve())
    try:
        _install(deckctl_path=resolved_deckctl, config_path=abs_config)
    except ServiceError as e:
        click.echo(str(e), err=True)
        sys.exit(6)
    click.echo(f"installed: systemd unit + udev rule; service active with --config {abs_config}")


@main.command("uninstall-service")
@click.option("--keep-udev", is_flag=True, help="Leave the udev rule in place; only remove the systemd unit.")
def uninstall_service(keep_udev: bool) -> None:
    """Stop + disable + remove the systemd unit (and udev rule unless --keep-udev)."""
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from deckctl.service import ServiceError
    from deckctl.service import uninstall_service as _uninstall
    try:
        _uninstall(remove_udev=not keep_udev)
    except ServiceError as e:
        click.echo(str(e), err=True)
        sys.exit(6)
    click.echo("uninstalled" + ("" if not keep_udev else " (udev rule kept)"))


@main.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Optional config file to validate.",
)
def doctor(config_path: str | None) -> None:
    """Report on device, dependencies, service status, and config."""
    from deckctl.doctor import Severity, render_report, run_all_checks
    results = run_all_checks(config_path=config_path)
    click.echo(render_report(results))
    if any(r.severity is Severity.FAIL for r in results):
        sys.exit(7)
