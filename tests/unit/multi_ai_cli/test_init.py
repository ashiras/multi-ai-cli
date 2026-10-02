"""Tests for multi_ai_cli.__init__ module."""

import multi_ai_cli


def test_package_has_version():
    assert hasattr(multi_ai_cli, "__version__")
    assert isinstance(multi_ai_cli.__version__, str)


def test_package_has_author():
    assert multi_ai_cli.__author__ == "Fumio SAGAWA"


def test_package_has_license():
    assert multi_ai_cli.__license__ == "MIT"