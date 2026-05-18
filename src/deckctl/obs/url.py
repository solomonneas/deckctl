"""Parse `obsws://host:port/password` URLs.

This is the single source of truth for OBS URL parsing — both the event
client and the action handlers use it.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ParsedObsws:
    host: str
    port: int
    password: str


def parse_obsws_url(url: str) -> ParsedObsws:
    """Parse a URL of the shape `obsws://host[:port][/password]`.

    Defaults: port=4455, password="" (empty string).
    Raises ValueError if the scheme is not obsws:// or the host is missing.
    """
    parsed = urlparse(url)
    if parsed.scheme != "obsws":
        raise ValueError(f"expected obsws:// URL, got scheme {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("obsws URL missing host")
    port = parsed.port if parsed.port is not None else 4455
    password = parsed.path.lstrip("/") if parsed.path else ""
    return ParsedObsws(host=parsed.hostname, port=port, password=password)
