import os
import pytest
from multi_ai_cli import config as app_config  # Import the module to access globals

@pytest.fixture(autouse=True)
def reset_globals():
    """
    Reset global variables in config.py before each test.
    This ensures tests run in isolation without affecting each other.
    """
    app_config.config.clear()
    app_config.INI_PATH = None
    # Yield control to the test function
    yield

def test_setup_config(tmp_path):
    """
    Test loading the INI configuration file into the global config object.
    """
    # Create a temporary INI file
    ini_file = tmp_path / "test.ini"
    ini_file.write_text("[API_KEYS]\ntest_key=12345\n", encoding="utf-8-sig")

    # Call the function
    app_config.setup_config(str(ini_file))

    # Verify global state is updated correctly
    assert app_config.INI_PATH == str(ini_file)
    assert app_config.config.get("API_KEYS", "test_key") == "12345"

def test_get_api_key_from_env(monkeypatch):
    """
    Test retrieving an API key primarily from an environment variable.
    """
    # Mock environment variable using pytest's monkeypatch
    monkeypatch.setenv("TEST_API_ENV", "env_secret_key")

    # Call the function
    key = app_config.get_api_key("test_key", "TEST_API_ENV")
    
    # Verify the key comes from the environment variable
    assert key == "env_secret_key"

def test_get_api_key_from_ini(tmp_path, monkeypatch):
    """
    Test retrieving an API key from the INI file when the env var is missing.
    """
    # Ensure the environment variable is NOT set
    monkeypatch.delenv("TEST_API_ENV", raising=False)

    # Setup the global config with a dummy INI file
    ini_file = tmp_path / "test.ini"
    ini_file.write_text("[API_KEYS]\ntest_key=ini_secret_key\n")
    app_config.setup_config(str(ini_file))

    # Call the function
    key = app_config.get_api_key("test_key", "TEST_API_ENV")
    
    # Verify the key comes from the INI file
    assert key == "ini_secret_key"

def test_get_api_key_missing(monkeypatch):
    """
    Test if ValueError is raised when the API key is completely missing.
    """
    # Ensure no environment variable is set
    monkeypatch.delenv("TEST_API_ENV", raising=False)
    app_config.INI_PATH = "dummy.ini"  # Set a dummy path for the error message
    
    # Expect a ValueError to be raised
    with pytest.raises(ValueError, match="is missing in"):
        app_config.get_api_key("test_key", "TEST_API_ENV")