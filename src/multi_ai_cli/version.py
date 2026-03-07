"""
Version information for the multi-ai-cli package.
This module retrieves the version string from the package metadata
defined during installation (e.g., via uv, pip, or pyproject.toml).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # Attempt to retrieve the package version installed in the environment.
    # The name must match the 'name' field in pyproject.toml.
    __version__ = version("multi-ai-cli")
except PackageNotFoundError:
    # Fallback to a development version string if the package is not
    # installed in the current environment (e.g., during local development).
    __version__ = "0.11.0"
