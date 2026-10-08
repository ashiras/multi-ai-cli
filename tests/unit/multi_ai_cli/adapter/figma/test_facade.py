import pytest

from multi_ai_cli.adapters.figma.facade import _parse_pull_args, _parse_push_args
from multi_ai_cli.adapters.figma.models import FigmaError


class TestFigmaArgumentParsing:
    def test_parse_pull_args_success(self):
        parts = [
            "@figma.pull",
            "--file",
            "abc-123",
            "--depth",
            "2",
            "--output-format",
            "raw-json",
            "-w",
            "out.json",
        ]
        request, write_file = _parse_pull_args(parts)
        assert request.file_key == "abc-123"
        assert request.depth == 2
        assert request.output_format == "raw-json"
        assert write_file == "out.json"

    def test_parse_pull_args_missing_file(self):
        with pytest.raises(FigmaError, match="--file <file_key> is required"):
            _parse_pull_args(["@figma.pull", "--depth", "1"])

    def test_parse_pull_args_conflicting_node_page(self):
        with pytest.raises(
            FigmaError, match="--node and --page cannot be used together"
        ):
            _parse_pull_args(
                ["@figma.pull", "--file", "f1", "--node", "1:1", "--page", "my-page"]
            )

    def test_parse_push_args_success(self, monkeypatch, tmp_path):
        # Use monkeypatch to control secure_resolve_path and the config
        # This ensures the test is deterministic and does not rely on global state
        d = tmp_path / "data"
        d.mkdir()
        f = d / "test.txt"
        f.write_text("content")

        def mock_resolve(path, base_dir, config):
            return d / path

        monkeypatch.setattr(
            "multi_ai_cli.adapters.figma.facade.secure_resolve_path", mock_resolve
        )

        parts = [
            "@figma.push",
            "-r",
            "test.txt",
            "--file",
            "f1",
            "--page",
            "p1",
            "--write",
            "out.json",
        ]

        request, write_file, content = _parse_push_args(parts)
        assert request.input_file == "test.txt"
        assert request.file_key == "f1"
        assert request.page == "p1"
        assert write_file == "out.json"
        assert content == "content"

    def test_parse_push_args_missing_read(self):
        with pytest.raises(FigmaError, match="-r <file> is required"):
            _parse_push_args(["@figma.push", "--file", "f1"])
