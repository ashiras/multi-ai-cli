import multi_ai_cli


def test_package_metadata():
    """
    Test if the package metadata in __init__.py is correctly defined.
    """
    # Check if version exists and is a string
    assert hasattr(multi_ai_cli, "__version__"), "__version__ is not defined"
    assert isinstance(multi_ai_cli.__version__, str), "__version__ must be a string"
    assert len(multi_ai_cli.__version__) > 0, "__version__ is empty"

    # Check if author name is correct
    assert multi_ai_cli.__author__ == "Fumio SAGAWA", (
        f"Expected 'Fumio SAGAWA', but got {multi_ai_cli.__author__}"
    )

    # Check if license is correct
    assert multi_ai_cli.__license__ == "MIT", (
        f"Expected 'MIT', but got {multi_ai_cli.__license__}"
    )


def test_package_docstring():
    """
    Test if the package docstring contains the expected tool name.
    """
    doc = multi_ai_cli.__doc__
    assert doc is not None, "Package docstring is missing"
    assert "multi-ai-cli" in doc, "Tool name not found in docstring"
