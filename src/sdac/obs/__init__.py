"""OBS WebSocket subscription + URL parsing.

The action execution path (handlers in `sdac.actions.obs`) shells out to the
`obs-cmd` binary on PATH — this package is just for event subscription and
URL parsing.
"""

from sdac.obs.url import ParsedObsws, parse_obsws_url

__all__ = ["ParsedObsws", "parse_obsws_url"]
