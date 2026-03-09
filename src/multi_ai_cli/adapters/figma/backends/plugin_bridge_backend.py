"""
Plugin bridge backend for ``@figma.push``.

Generates a handoff JSON file that a Figma-side plugin can import.
Does **not** call the Figma Plugin API directly and does **not**
require a ``FIGMA_ACCESS_TOKEN``.
"""

from __future__ import annotations

import json
import os
import time

from ..models import (
    FigmaError,
    FigmaPushRequest,
    FigmaPushResponse,
    HandoffPayload,
)


class PluginBridgeBackend:
    """Writes handoff payloads for consumption by a Figma plugin.

    Args:
        handoff_dir: Directory where handoff JSON files are placed.
    """

    def __init__(self, handoff_dir: str) -> None:
        """Initialize the Plugin Bridge backend with a handoff directory."""
        self.handoff_dir = handoff_dir

    def push(self, request: FigmaPushRequest, content: str) -> FigmaPushResponse:
        """Creates a handoff JSON file from the push request.

        Args:
            request: Push parameters.
            content: The raw content read from the input file.

        Returns:
            FigmaPushResponse with the path to the generated file.

        Raises:
            FigmaError: If the input format cannot be determined.
        """
        fmt = request.input_format or self._detect_input_format(request.input_file)

        payload = HandoffPayload(
            input_format=fmt,
            source_file=request.input_file,
            target={
                k: v
                for k, v in {
                    "file_key": request.file_key,
                    "page": request.page,
                    "frame": request.frame,
                }.items()
                if v is not None
            },
            content=content,
        )

        os.makedirs(self.handoff_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"handoff_{timestamp}.json"
        handoff_path = os.path.join(self.handoff_dir, filename)

        with open(handoff_path, "w", encoding="utf-8") as f:
            json.dump(payload.to_dict(), f, indent=2, ensure_ascii=False)

        return FigmaPushResponse(
            success=True,
            message=f"Handoff payload written to '{handoff_path}'",
            handoff_path=handoff_path,
            target=payload.target,
        )

    # ------------------------------------------------------------------

    def _detect_input_format(self, filename: str) -> str:
        """Infers ``input_format`` from the file extension.

        Raises:
            FigmaError: If the extension is not recognised.
        """
        if filename.endswith(".md"):
            return "markdown"
        if filename.endswith(".json"):
            return "json"
        raise FigmaError(
            f"@figma.push: unsupported input format for '{filename}'. "
            "Use --input-format to specify."
        )
