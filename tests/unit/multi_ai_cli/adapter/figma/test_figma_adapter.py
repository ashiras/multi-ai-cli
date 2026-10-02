"""Tests for multi_ai_cli.adapters.figma.adapter module."""

from unittest.mock import MagicMock

import pytest

from multi_ai_cli.adapters.figma.adapter import FigmaAdapter
from multi_ai_cli.adapters.figma.models import (
    FigmaError,
    FigmaPullRequest,
    FigmaPullResponse,
    FigmaPushRequest,
    FigmaPushResponse,
    NormalizedNode,
)


class TestFigmaAdapterPull:
    def test_pull_no_backend(self):
        adapter = FigmaAdapter(pull_backend=None, push_backend=None)
        request = FigmaPullRequest(file_key="abc123")
        with pytest.raises(FigmaError, match="REST backend is not available"):
            adapter.pull(request)

    def test_pull_raw_json(self):
        mock_backend = MagicMock()
        raw_data = {"document": {"id": "0:0"}}
        mock_backend.pull.return_value = raw_data

        adapter = FigmaAdapter(pull_backend=mock_backend)
        request = FigmaPullRequest(file_key="abc123", output_format="raw-json")
        response = adapter.pull(request)

        assert isinstance(response, FigmaPullResponse)
        assert response.data == raw_data
        assert response.raw == raw_data

    def test_pull_normalized_file(self):
        mock_backend = MagicMock()
        raw_data = {
            "document": {
                "id": "0:0",
                "name": "Document",
                "type": "DOCUMENT",
                "children": [],
            }
        }
        mock_backend.pull.return_value = raw_data

        adapter = FigmaAdapter(pull_backend=mock_backend)
        request = FigmaPullRequest(file_key="abc123")
        response = adapter.pull(request)

        assert isinstance(response, FigmaPullResponse)
        assert isinstance(response.data, NormalizedNode)
        assert response.data.kind == "document"

    def test_pull_normalized_node(self):
        mock_backend = MagicMock()
        raw_data = {
            "nodes": {
                "1:2": {
                    "document": {
                        "id": "1:2",
                        "name": "Button",
                        "type": "FRAME",
                        "children": [],
                    }
                }
            }
        }
        mock_backend.pull.return_value = raw_data

        adapter = FigmaAdapter(pull_backend=mock_backend)
        request = FigmaPullRequest(file_key="abc123", node_id="1:2")
        response = adapter.pull(request)

        assert isinstance(response.data, NormalizedNode)
        assert response.data.node_id == "1:2"

    def test_pull_normalized_with_page(self):
        mock_backend = MagicMock()
        raw_data = {
            "document": {
                "id": "0:0",
                "name": "Document",
                "type": "DOCUMENT",
                "children": [
                    {"id": "1:0", "name": "MyPage", "type": "CANVAS", "children": []},
                ],
            }
        }
        mock_backend.pull.return_value = raw_data

        adapter = FigmaAdapter(pull_backend=mock_backend)
        request = FigmaPullRequest(file_key="abc123", page="MyPage")
        response = adapter.pull(request)

        assert isinstance(response.data, NormalizedNode)
        assert response.data.node_name == "MyPage"


class TestFigmaAdapterPush:
    def test_push_no_backend(self):
        adapter = FigmaAdapter(pull_backend=None, push_backend=None)
        request = FigmaPushRequest(input_file="test.md")
        with pytest.raises(FigmaError, match="plugin bridge is not available"):
            adapter.push(request, "content")

    def test_push_success(self):
        mock_push = MagicMock()
        mock_push.push.return_value = FigmaPushResponse(
            success=True, message="OK", handoff_path="/tmp/h.json"
        )

        adapter = FigmaAdapter(push_backend=mock_push)
        request = FigmaPushRequest(input_file="test.md")
        response = adapter.push(request, "content")

        assert response.success is True
        mock_push.push.assert_called_once_with(request, "content")

