r"""
Command-line splitting that keeps Windows path separators intact.

``shlex.split`` treats a backslash as an escape character, which turns
``sub\x.md`` into ``subx.md``. On Windows a backslash is far more likely
to be a path separator, so it is kept literal unless it escapes a quote,
another backslash or a space.
"""

import re
import shlex
import sys

_LITERAL_BACKSLASH = re.compile(r"\\(?![\\\"' ])")


def split_command(text: str) -> list[str]:
    """
    Split a command line into tokens like ``shlex.split``.

    On non-Windows platforms this is exactly ``shlex.split``. On Windows,
    a backslash that does not precede a quote, a backslash or a space is
    treated as a literal character.

    Args:
        text (str): The command line to split.

    Returns:
        list[str]: The parsed tokens.

    Raises:
        ValueError: If the text contains an unterminated quotation.
    """
    if sys.platform == "win32":
        text = _LITERAL_BACKSLASH.sub(r"\\\\", text)
    return shlex.split(text)
