"""
Figma artifact adapter.

Orchestrates pull / push operations by delegating to the appropriate
backend and normalisation functions.  Business logic lives here so
that the facade layer can stay thin.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .backends.plugin_bridge_backend import PluginBridgeBackend
from .backends.rest_backend import RestBackend
from .models import (
    FigmaError,
    FigmaPullRequest,
    FigmaPullResponse,
    FigmaPushRequest,
    FigmaPushResponse,
)
from .normalize import normalize_file_response, normalize_nodes_response


class ArtifactAdapter(ABC):
    """Abstract base for design-artifact adapters.

    Provides a common interface so that future adapters (Notion, Jira,
    GitHub, …) can be swapped in without changing the facade layer.
    """

    @abstractmethod
    def pull(self, request: Any) -> Any:
        """Pull data or assets from Figma."""
        ...

    @abstractmethod
    def push(self, request: Any, content: str) -> Any:
        """Push data or assets to Figma."""
        ...


class FigmaAdapter(ArtifactAdapter):
    """Concrete adapter for Figma workspaces.

    Delegates to ``RestBackend`` for pulls and
    ``PluginBridgeBackend`` for pushes.

    Future backends (not implemented in MVP):
      - ``McpBackend``       – MCP-based context retrieval
      - ``FigmaUseBackend``  – direct CLI manipulation via figma-use
    """

    def __init__(
        self,
        pull_backend: RestBackend | None = None,
        push_backend: PluginBridgeBackend | None = None,
    ) -> None:
        """Initialize the Figma adapter."""
        self.pull_backend = pull_backend
        self.push_backend = push_backend

    def pull(self, request: FigmaPullRequest) -> FigmaPullResponse:
        """Fetches and optionally normalises design data.

        The *file* and *nodes* endpoints return differently shaped
        responses, so the correct normalisation function is selected
        based on the presence of ``request.node_id``.

        Args:
            request: Pull parameters.

        Returns:
            FigmaPullResponse: Normalised or raw design data.

        Raises:
            FigmaError: If no pull backend is configured or the API
                call / normalisation fails.
        """
        if self.pull_backend is None:
            raise FigmaError(
                "@figma.pull: REST backend is not available. "
                "Set FIGMA_ACCESS_TOKEN to use @figma.pull."
            )

        raw = self.pull_backend.pull(request)

        if request.output_format == "raw-json":
            return FigmaPullResponse(data=raw, raw=raw)

        # normalized-json (default)
        if request.node_id:
            normalized = normalize_nodes_response(
                raw_json=raw,
                file_key=request.file_key,
            )
        else:
            normalized = normalize_file_response(
                raw_json=raw,
                file_key=request.file_key,
                page_filter=request.page,
            )

        return FigmaPullResponse(data=normalized, raw=raw)

    def push(self, request: FigmaPushRequest, content: str) -> FigmaPushResponse:
        """Writes a handoff payload for the Figma-side plugin.

        No ``FIGMA_ACCESS_TOKEN`` is required — this operation is
        purely local file I/O.

        Args:
            request: Push parameters.
            content: Raw content of the input file.

        Returns:
            FigmaPushResponse: Operation result.

        Raises:
            FigmaError: If no push backend is configured.
        """
        if self.push_backend is None:
            raise FigmaError("@figma.push: plugin bridge is not available")

        return self.push_backend.push(request, content)
