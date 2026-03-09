"""
REST API backend for ``@figma.pull``.

Uses the official Figma REST API to fetch file and node data.
"""

from __future__ import annotations

import requests

from ..models import FigmaError, FigmaPullRequest


class RestBackend:
    """Fetches design data from Figma via the REST API.

    Args:
        access_token: A valid Figma personal access token.
    """

    def __init__(self, access_token: str) -> None:
        """Initialize the Figma REST API backend."""
        self.access_token = access_token
        self.base_url = "https://api.figma.com/v1"

    def _headers(self) -> dict[str, str]:
        return {"X-Figma-Token": self.access_token}

    def pull(self, request: FigmaPullRequest) -> dict:
        """Fetches raw JSON from the Figma API.

        Selects the *nodes* endpoint when ``request.node_id`` is set,
        otherwise uses the *file* endpoint.

        Args:
            request: Pull parameters.

        Returns:
            dict: The raw API response body.

        Raises:
            FigmaError: On HTTP errors (auth, not-found, etc.).
        """
        if request.node_id:
            url = f"{self.base_url}/files/{request.file_key}/nodes"
            params: dict[str, str] = {"ids": request.node_id}
            if request.depth is not None:
                params["depth"] = str(request.depth)
        else:
            url = f"{self.base_url}/files/{request.file_key}"
            params = {}
            if request.depth is not None:
                params["depth"] = str(request.depth)

        response = requests.get(url, headers=self._headers(), params=params)
        self._check_response(response, request)
        return response.json()

    # ------------------------------------------------------------------

    def _check_response(
        self, response: requests.Response, request: FigmaPullRequest
    ) -> None:
        """Translates HTTP status codes into ``FigmaError``."""
        if response.status_code == 200:
            return
        if response.status_code == 403:
            raise FigmaError(
                "@figma.pull: Access denied. "
                "Check FIGMA_ACCESS_TOKEN and file permissions."
            )
        if response.status_code == 404:
            if request.node_id:
                raise FigmaError(
                    f"@figma.pull: node '{request.node_id}' not found "
                    f"in file '{request.file_key}'."
                )
            raise FigmaError(f"@figma.pull: file '{request.file_key}' not found.")
        raise FigmaError(
            f"@figma.pull: Figma API returned status {response.status_code}"
        )
