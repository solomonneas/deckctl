"""Allow `python -m sdac`."""

# TODO(Task 2): wire src/sdac/cli.py; suppress until module ships with py.typed/stubs.
from sdac.cli import main  # type: ignore[import-untyped]

if __name__ == "__main__":
    main()
