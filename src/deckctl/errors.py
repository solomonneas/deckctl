"""Exception hierarchy for deckctl.

All custom exceptions inherit from SdacError so callers can catch the
package's errors without catching unrelated exceptions.
"""


class SdacError(Exception):
    """Base class for all deckctl errors."""


class ConfigError(SdacError):
    """Raised when a config file cannot be loaded or validated."""


class ConfigPermissionError(ConfigError):
    """Raised when the config file's POSIX permissions are too open."""


class EnvVarMissingError(ConfigError):
    """Raised when a `${VAR}` substitution refers to an unset env var."""


class RenderError(SdacError):
    """Raised when an icon cannot be rendered (asset missing, bad spec, etc.)."""
