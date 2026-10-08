"""Tests for multi_ai_cli.version module."""

import importlib
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import multi_ai_cli.version
from multi_ai_cli.version import __version__


def test_version_is_string():
    assert isinstance(__version__, str)


def test_version_not_empty():
    assert len(__version__) > 0


def test_version_format():
    """Version should be a semver-like string."""
    parts = __version__.split(".")
    assert len(parts) >= 2
    for part in parts:
        assert part.isdigit() or "-" in part or "+" in part


def test_version_fallback_on_package_not_found():
    """Test that __version__ defaults to 0.11.0 when PackageNotFoundError occurs."""
    with patch(
        "importlib.metadata.version",
        side_effect=PackageNotFoundError,
    ):
        importlib.reload(multi_ai_cli.version)
        assert multi_ai_cli.version.__version__ == "0.11.0"

    # Restore original module state
    importlib.reload(multi_ai_cli.version)


def test_version_retrieval_success():
    """Test that __version__ correctly captures the metadata version string."""
    with patch(
        "importlib.metadata.version",
        return_value="1.2.3",
    ):
        importlib.reload(multi_ai_cli.version)
        assert multi_ai_cli.version.__version__ == "1.2.3"

    # Restore original module state
    importlib.reload(multi_ai_cli.version)
