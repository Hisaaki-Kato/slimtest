"""slimtest — factory + trait DSL on top of dbt unit tests."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("slimtest")
except PackageNotFoundError:  # not installed (e.g. running from a clean source tree)
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
