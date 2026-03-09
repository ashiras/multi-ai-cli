"""
Version information for the multi-ai-cli package.

This module retrieves the version string from the package metadata
defined during installation (e.g., via uv, pip, or pyproject.toml).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("multi-ai-cli")
except PackageNotFoundError:
    __version__ = "0.11.0"
