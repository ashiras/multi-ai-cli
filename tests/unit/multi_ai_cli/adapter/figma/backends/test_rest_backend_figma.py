"""Tests for multi_ai_cli.adapters.figma.backends.rest_backend module."""

from unittest.mock import MagicMock, patch

import pytest

from multi_ai_cli.adapters.figma.backends.rest_backend import RestBackend
from multi_ai_cli.adapters.figma.models import FigmaError, FigmaPullRequest


class TestRestBackend:
    def setup_method(self):
        self.backend = RestBackend(access_token="test_token")

    def test_headers(self):
        h = self.backend._headers()
        assert h["X-Figma-Token"] == "test_token"

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_file(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"document": {"id": "0:0"}}
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123")
        result = self.backend.pull(request)
        assert result["document"]["id"] == "0:0"

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "files/abc123" in args[0]
        assert "ids" not in kwargs.get("params", {})

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_node(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"nodes": {"1:2": {"document": {}}}}
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123", node_id="1:2")
        result = self.backend.pull(request)
        assert "nodes" in result

        args, kwargs = mock_get.call_args
        assert "nodes" in args[0]
        assert kwargs["params"]["ids"] == "1:2"

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_with_depth(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"document": {}}
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123", depth=2)
        self.backend.pull(request)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["depth"] == "2"

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_403(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123")
        with pytest.raises(FigmaError, match="Access denied"):
            self.backend.pull(request)

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_404_file(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123")
        with pytest.raises(FigmaError, match="file 'abc123' not found"):
            self.backend.pull(request)

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_404_node(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123", node_id="99:99")
        with pytest.raises(FigmaError, match="node '99:99' not found"):
            self.backend.pull(request)

    @patch("multi_ai_cli.adapters.figma.backends.rest_backend.requests.get")
    def test_pull_500(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        request = FigmaPullRequest(file_key="abc123")
        with pytest.raises(FigmaError, match="status 500"):
            self.backend.pull(request)