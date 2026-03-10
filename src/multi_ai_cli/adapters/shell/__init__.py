"""Shell adapter for Multi-AI CLI."""

from .adapter import ShellAdapter
from .models import ParsedShInput, ShellResult

__all__ = ["ShellAdapter", "ParsedShInput", "ShellResult"]
