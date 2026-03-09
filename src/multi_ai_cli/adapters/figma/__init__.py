"""Figma design interface adapter for multi-ai-cli."""

from .facade import handle_figma_pull, handle_figma_push
from .models import FigmaError

__all__ = ["handle_figma_pull", "handle_figma_push", "FigmaError"]
