"""Tests for multi_ai_cli.adapters.figma.normalize module."""

import pytest

from multi_ai_cli.adapters.figma.models import FigmaError, NormalizedNode
from multi_ai_cli.adapters.figma.normalize import (
    _convert_node,
    _find_page,
    normalize_file_response,
    normalize_nodes_response,
)


class TestNormalizeFileResponse:
    def test_basic_file_response(self):
        raw = {
            "document": {
                "id": "0:0",
                "name": "Document",
                "type": "DOCUMENT",
                "children": [
                    {
                        "id": "1:0",
                        "name": "Page 1",
                        "type": "CANVAS",
                        "children": [],
                    }
                ],
            }
        }
        result = normalize_file_response(raw, "file123")
        assert isinstance(result, NormalizedNode)
        assert result.file_key == "file123"
        assert result.kind == "document"

    def test_with_page_filter(self):
        raw = {
            "document": {
                "id": "0:0",
                "name": "Document",
                "type": "DOCUMENT",
                "children": [
                    {"id": "1:0", "name": "Page A", "type": "CANVAS", "children": []},
                    {"id": "2:0", "name": "Page B", "type": "CANVAS", "children": []},
                ],
            }
        }
        result = normalize_file_response(raw, "file123", page_filter="Page B")
        assert result.node_name == "Page B"
        assert result.page == "Page B"

    def test_page_not_found(self):
        raw = {
            "document": {
                "id": "0:0",
                "name": "Document",
                "type": "DOCUMENT",
                "children": [
                    {"id": "1:0", "name": "Page A", "type": "CANVAS", "children": []}
                ],
            }
        }
        with pytest.raises(FigmaError, match="page 'Missing' not found"):
            normalize_file_response(raw, "file123", page_filter="Missing")

    def test_no_document_field(self):
        with pytest.raises(FigmaError, match="no 'document' field"):
            normalize_file_response({}, "file123")


class TestNormalizeNodesResponse:
    def test_basic_nodes_response(self):
        raw = {
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
        result = normalize_nodes_response(raw, "file123")
        assert isinstance(result, NormalizedNode)
        assert result.node_id == "1:2"
        assert result.node_name == "Button"
        assert result.kind == "frame"

    def test_no_nodes_field(self):
        with pytest.raises(FigmaError, match="no 'nodes' field"):
            normalize_nodes_response({}, "file123")

    def test_no_document_in_node(self):
        raw = {"nodes": {"1:2": {}}}
        with pytest.raises(FigmaError, match="no 'document'"):
            normalize_nodes_response(raw, "file123")


class TestFindPage:
    def test_no_filter(self):
        doc = {"name": "Doc", "children": []}
        result = _find_page(doc, None)
        assert result is doc

    def test_filter_found(self):
        doc = {
            "children": [
                {"name": "Page A", "type": "CANVAS"},
                {"name": "Page B", "type": "CANVAS"},
            ]
        }
        result = _find_page(doc, "Page B")
        assert result["name"] == "Page B"

    def test_filter_not_found(self):
        doc = {"children": [{"name": "Page A"}]}
        with pytest.raises(FigmaError, match="not found"):
            _find_page(doc, "Missing")


class TestConvertNode:
    def test_basic_node(self):
        node = {
            "id": "1:0",
            "name": "Frame",
            "type": "FRAME",
            "absoluteBoundingBox": {"x": 10, "y": 20, "width": 100, "height": 200},
            "children": [],
            "visible": True,
        }
        result = _convert_node(node, "file123", "Page 1")
        assert result.node_id == "1:0"
        assert result.node_name == "Frame"
        assert result.kind == "frame"
        assert result.layout == {"x": 10, "y": 20, "width": 100, "height": 200}
        assert result.meta == {"visible": True}

    def test_text_node(self):
        node = {
            "id": "2:0",
            "name": "Label",
            "type": "TEXT",
            "characters": "Hello World",
            "children": [],
        }
        result = _convert_node(node, "file123", "")
        assert result.text == ["Hello World"]

    def test_text_node_empty_characters(self):
        node = {
            "id": "2:0",
            "name": "Label",
            "type": "TEXT",
            "characters": "",
            "children": [],
        }
        result = _convert_node(node, "file123", "")
        assert result.text == []

    def test_non_text_node_has_no_text(self):
        node = {
            "id": "1:0",
            "name": "Frame",
            "type": "FRAME",
            "children": [],
        }
        result = _convert_node(node, "file123", "")
        assert result.text == []

    def test_recursive_children(self):
        node = {
            "id": "1:0",
            "name": "Parent",
            "type": "FRAME",
            "children": [
                {
                    "id": "2:0",
                    "name": "Child",
                    "type": "RECTANGLE",
                    "children": [],
                }
            ],
        }
        result = _convert_node(node, "file123", "")
        assert len(result.children) == 1
        assert result.children[0].node_name == "Child"

    def test_no_bounding_box(self):
        node = {"id": "1:0", "name": "X", "type": "FRAME", "children": []}
        result = _convert_node(node, "f", "")
        assert result.layout == {"x": 0, "y": 0, "width": 0, "height": 0}

    def test_missing_fields(self):
        node = {}
        result = _convert_node(node, "f", "p")
        assert result.node_id == ""
        assert result.node_name == ""
        assert result.kind == ""
        assert result.meta == {"visible": True}

    def test_nested_text_extraction(self):
        node = {
            "id": "1:0",
            "name": "Parent",
            "type": "FRAME",
            "children": [
                {
                    "id": "2:0",
                    "name": "Child Text",
                    "type": "TEXT",
                    "characters": "Hello",
                }
            ],
        }
        result = _convert_node(node, "file123", "")
        assert len(result.children) == 1
        assert result.children[0].text == ["Hello"]

    def test_visible_defaults_to_true(self):
        node = {"id": "1:0", "name": "Frame", "type": "FRAME"}
        result = _convert_node(node, "file123", "")
        assert result.meta == {"visible": True}
        assert result.meta == {"visible": True}
