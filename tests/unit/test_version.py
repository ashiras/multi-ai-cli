import importlib
from importlib.metadata import PackageNotFoundError

import pytest

# Load the `multi_ai_cli.version` module once.
# This makes `importlib.reload()` available.
# At this point, `__version__` is the actual value, but we'll reload it in tests to apply mocks.
from multi_ai_cli import version as app_version


def test_version_found(mocker):
    """
    Tests the case where the package version is found.
    """
    # Mock importlib.metadata.version to return "1.0.0"
    mock_version = mocker.patch("importlib.metadata.version", return_value="1.0.0")

    # Reload the module so the mocked version() function is used
    importlib.reload(app_version)

    # Assert that the reloaded module's __version__ matches the mocked value
    assert app_version.__version__ == "1.0.0"
    mock_version.assert_called_once_with("multi-ai-cli")


def test_version_not_found(mocker):
    """
    Tests the case where the package version is not found (PackageNotFoundError).
    """
    # Mock importlib.metadata.version to raise PackageNotFoundError
    mock_version = mocker.patch(
        "importlib.metadata.version", side_effect=PackageNotFoundError
    )

    # Reload the module so the mocked version() function is used,
    # causing PackageNotFoundError and setting the fallback value.
    importlib.reload(app_version)

    # Assert that the reloaded module's __version__ matches the fallback value
    assert app_version.__version__ == "0.11.0"
    mock_version.assert_called_once_with("multi-ai-cli")


if __name__ == "__main__":
    pytest.main()
