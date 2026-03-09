"""
Data models for the Figma adapter.

Contains request/response dataclasses, the normalized intermediate
representation, the handoff payload contract, and the adapter-specific
exception class.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class FigmaError(Exception):
    """Figma adapter specific error."""

    pass


@dataclass
class FigmaPullRequest:
    """Parameters for a ``@figma.pull`` operation.

    Attributes:
        file_key: Figma file key (required).
        node_id: Specific node to fetch via the nodes endpoint.
        page: Page name to extract (mutually exclusive with *node_id*).
        depth: Traversal depth passed to the Figma API.
        output_format: Desired output format (``raw-json`` or
            ``normalized-json``).
    """

    file_key: str
    node_id: str | None = None
    page: str | None = None
    depth: int | None = None
    output_format: str = "normalized-json"


@dataclass
class FigmaPushRequest:
    """Parameters for a ``@figma.push`` operation.

    Attributes:
        input_file: Path to the input file specified via ``-r``.
        file_key: Target Figma file key (optional metadata).
        page: Target page name (optional metadata).
        frame: Target frame name (optional metadata).
        input_format: Semantic type of the input data (``markdown``,
            ``json``, etc.).  Auto-detected from extension when *None*.
    """

    input_file: str
    file_key: str | None = None
    page: str | None = None
    frame: str | None = None
    input_format: str | None = None


@dataclass
class NormalizedNode:
    """Minimal intermediate representation of a Figma node.

    MVP fields cover the structural skeleton required by downstream
    consumers (LLM prompts, codegen, tests).  Detailed style, variable,
    and component information is deferred to future iterations.
    """

    source: str = "figma"
    file_key: str = ""
    page: str = ""
    node_id: str = ""
    node_name: str = ""
    kind: str = ""
    layout: dict = field(default_factory=dict)
    children: list[NormalizedNode] = field(default_factory=list)
    text: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Converts the node tree to a plain dictionary."""
        return {
            "source": self.source,
            "file_key": self.file_key,
            "page": self.page,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "kind": self.kind,
            "layout": self.layout,
            "children": [c.to_dict() for c in self.children],
            "text": self.text,
            "meta": self.meta,
        }


@dataclass
class FigmaPullResponse:
    """Result of a ``@figma.pull`` operation.

    Attributes:
        data: Normalized node tree or raw dictionary depending on
            *output_format*.
        raw: The unmodified API response for debugging / raw-json mode.
    """

    data: NormalizedNode | dict
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialises the response for JSON output."""
        if isinstance(self.data, NormalizedNode):
            return self.data.to_dict()
        return self.data


@dataclass
class FigmaPushResponse:
    """Result of a ``@figma.push`` operation.

    Attributes:
        success: Whether the handoff payload was written successfully.
        message: Human-readable status message.
        handoff_path: Filesystem path to the generated handoff JSON.
        target: Metadata echoing the intended Figma target.
    """

    success: bool
    message: str
    handoff_path: str | None = None
    target: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialises the response for JSON output."""
        return {
            "success": self.success,
            "message": self.message,
            "handoff_path": self.handoff_path,
            "target": self.target,
        }


@dataclass
class HandoffPayload:
    """Contract for the JSON file consumed by the Figma-side plugin.

    The *version* field allows the plugin to handle schema evolution
    without breaking existing consumers.
    """

    type: str = "figma_handoff"
    version: int = 1
    input_format: str = ""
    source_file: str = ""
    target: dict = field(default_factory=dict)
    content: str = ""

    def to_dict(self) -> dict:
        """Serialises the payload for JSON output."""
        return {
            "type": self.type,
            "version": self.version,
            "input_format": self.input_format,
            "source_file": self.source_file,
            "target": self.target,
            "content": self.content,
        }
