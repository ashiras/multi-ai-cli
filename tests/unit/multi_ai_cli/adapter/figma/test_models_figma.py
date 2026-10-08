"""Tests for multi_ai_cli.adapters.figma.models module."""

from multi_ai_cli.adapters.figma.models import (
    FigmaError,
    FigmaPullRequest,
    FigmaPullResponse,
    FigmaPushRequest,
    FigmaPushResponse,
    HandoffPayload,
    NormalizedNode,
)


class TestFigmaError:
    def test_is_exception(self):
        err = FigmaError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"


class TestFigmaPullRequest:
    def test_defaults(self):
        req = FigmaPullRequest(file_key="abc123")
        assert req.file_key == "abc123"
        assert req.node_id is None
        assert req.page is None
        assert req.depth is None
        assert req.output_format == "normalized-json"

    def test_all_fields(self):
        req = FigmaPullRequest(
            file_key="abc",
            node_id="1:2",
            page="Page 1",
            depth=3,
            output_format="raw-json",
        )
        assert req.node_id == "1:2"
        assert req.page == "Page 1"
        assert req.depth == 3
        assert req.output_format == "raw-json"

    def test_mutually_exclusive_params_allowed(self):
        # FigmaPullRequest is a dataclass without internal validation.
        # This test documents that both can be set simultaneously.
        req = FigmaPullRequest(file_key="abc", node_id="1:2", page="Page 1")
        assert req.node_id == "1:2"
        assert req.page == "Page 1"

    def test_missing_required_file_key(self):
        # Verify that TypeError is raised if file_key is omitted,
        # confirming basic dataclass constructor enforcement.
        try:
            FigmaPullRequest()
        except TypeError:
            pass
        else:
            assert False, "FigmaPullRequest should require file_key"


class TestFigmaPushRequest:
    def test_defaults(self):
        req = FigmaPushRequest(input_file="test.md")
        assert req.input_file == "test.md"
        assert req.file_key is None
        assert req.page is None
        assert req.frame is None
        assert req.input_format is None

    def test_all_fields(self):
        req = FigmaPushRequest(
            input_file="test.md",
            file_key="abc",
            page="Page 1",
            frame="Frame 1",
            input_format="markdown",
        )
        assert req.file_key == "abc"
        assert req.frame == "Frame 1"
        assert req.input_format == "markdown"


class TestNormalizedNode:
    def test_defaults(self):
        node = NormalizedNode()
        assert node.source == "figma"
        assert node.file_key == ""
        assert node.page == ""
        assert node.node_id == ""
        assert node.node_name == ""
        assert node.kind == ""
        assert node.layout == {}
        assert node.children == []
        assert node.text == []
        assert node.meta == {}

    def test_to_dict(self):
        child = NormalizedNode(node_id="child1", kind="text")
        parent = NormalizedNode(
            file_key="abc",
            page="Page 1",
            node_id="parent",
            node_name="Frame",
            kind="frame",
            layout={"x": 10, "y": 20, "width": 100, "height": 200},
            children=[child],
            text=["Hello"],
            meta={"visible": True},
        )
        d = parent.to_dict()
        assert d["file_key"] == "abc"
        assert d["node_id"] == "parent"
        assert d["kind"] == "frame"
        assert len(d["children"]) == 1
        assert d["children"][0]["node_id"] == "child1"
        assert d["text"] == ["Hello"]
        assert d["meta"]["visible"] is True

    def test_to_dict_recursive(self):
        grandchild = NormalizedNode(node_id="gc")
        child = NormalizedNode(node_id="c", children=[grandchild])
        root = NormalizedNode(node_id="r", children=[child])
        d = root.to_dict()
        assert d["children"][0]["children"][0]["node_id"] == "gc"


class TestFigmaPullResponse:
    def test_with_normalized_node(self):
        node = NormalizedNode(node_id="test")
        resp = FigmaPullResponse(data=node, raw={"raw": "data"})
        d = resp.to_dict()
        assert d["node_id"] == "test"

    def test_with_raw_dict(self):
        resp = FigmaPullResponse(data={"key": "value"}, raw={"raw": True})
        d = resp.to_dict()
        assert d == {"key": "value"}

    def test_default_raw(self):
        node = NormalizedNode()
        resp = FigmaPullResponse(data=node)
        assert resp.raw == {}


class TestFigmaPushResponse:
    def test_to_dict(self):
        resp = FigmaPushResponse(
            success=True,
            message="Done",
            handoff_path="/tmp/handoff.json",
            target={"file_key": "abc"},
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["message"] == "Done"
        assert d["handoff_path"] == "/tmp/handoff.json"
        assert d["target"]["file_key"] == "abc"

    def test_defaults(self):
        resp = FigmaPushResponse(success=False, message="Failed")
        assert resp.handoff_path is None
        assert resp.target == {}


class TestHandoffPayload:
    def test_defaults(self):
        hp = HandoffPayload()
        assert hp.type == "figma_handoff"
        assert hp.version == 1
        assert hp.input_format == ""
        assert hp.source_file == ""
        assert hp.target == {}
        assert hp.content == ""

    def test_to_dict(self):
        hp = HandoffPayload(
            input_format="markdown",
            source_file="req.md",
            target={"file_key": "abc"},
            content="# Hello",
        )
        d = hp.to_dict()
        assert d["type"] == "figma_handoff"
        assert d["version"] == 1
        assert d["input_format"] == "markdown"
        assert d["source_file"] == "req.md"
        assert d["target"]["file_key"] == "abc"
        assert d["content"] == "# Hello"
