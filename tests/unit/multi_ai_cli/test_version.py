"""Tests for multi_ai_cli.version module."""

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