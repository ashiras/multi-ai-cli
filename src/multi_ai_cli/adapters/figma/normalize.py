"""
Figma response normalisation.

Converts raw Figma REST API JSON into the ``NormalizedNode``
intermediate representation.  Separate entry points are provided for
the *file* endpoint and the *nodes* endpoint because their response
shapes differ.
"""

from __future__ import annotations

from .models import FigmaError, NormalizedNode


def normalize_file_response(
    raw_json: dict,
    file_key: str,
    page_filter: str | None = None,
) -> NormalizedNode:
    """Normalises a ``/v1/files/{key}`` response.

    The file endpoint returns::

        { "document": { "children": [ ...pages... ] }, ... }

    When *page_filter* is given only the matching page is converted.

    Args:
        raw_json: Raw JSON from the Figma file endpoint.
        file_key: The Figma file key used in the request.
        page_filter: Optional page name to extract.

    Returns:
        NormalizedNode: The converted node tree.

    Raises:
        FigmaError: If the response lacks a ``document`` field or the
            requested page is not found.
    """
    document = raw_json.get("document")
    if not document:
        raise FigmaError("@figma.pull: response has no 'document' field.")

    target = _find_page(document, page_filter)
    return _convert_node(target, file_key, page_filter or "")


def normalize_nodes_response(
    raw_json: dict,
    file_key: str,
) -> NormalizedNode:
    """Normalises a ``/v1/files/{key}/nodes?ids=`` response.

    The nodes endpoint returns::

        { "nodes": { "<id>": { "document": { ... } } } }

    MVP assumes a single node id and returns the first entry.

    Args:
        raw_json: Raw JSON from the Figma nodes endpoint.
        file_key: The Figma file key used in the request.

    Returns:
        NormalizedNode: The converted node tree.

    Raises:
        FigmaError: If the response lacks a ``nodes`` field or the node
            entry has no ``document``.
    """
    nodes = raw_json.get("nodes")
    if not nodes:
        raise FigmaError("@figma.pull: response has no 'nodes' field.")

    first_id = next(iter(nodes))
    node_entry = nodes[first_id]
    node_doc = node_entry.get("document")
    if not node_doc:
        raise FigmaError(
            f"@figma.pull: node '{first_id}' has no 'document' in response."
        )

    return _convert_node(node_doc, file_key, "")


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _find_page(document: dict, page_filter: str | None) -> dict:
    """Locates a page inside ``document.children``.

    Returns the full document when *page_filter* is ``None``.

    Raises:
        FigmaError: If the requested page name is not found.
    """
    if page_filter is None:
        return document
    for child in document.get("children", []):
        if child.get("name") == page_filter:
            return child
    raise FigmaError(f"@figma.pull: page '{page_filter}' not found in document")


def _convert_node(node: dict, file_key: str, page: str) -> NormalizedNode:
    """Recursively converts a Figma node dict to ``NormalizedNode``.

    MVP extracts the structural skeleton only:
    - ``layout`` from ``absoluteBoundingBox``
    - ``children`` via recursion
    - ``text`` from ``TEXT`` node ``characters``
    - ``meta.visible``
    """
    bounds = node.get("absoluteBoundingBox") or {}

    children = [_convert_node(c, file_key, page) for c in node.get("children", [])]

    text: list[str] = []
    if node.get("type") == "TEXT":
        characters = node.get("characters", "")
        if characters:
            text.append(characters)

    return NormalizedNode(
        file_key=file_key,
        page=page,
        node_id=node.get("id", ""),
        node_name=node.get("name", ""),
        kind=node.get("type", "").lower(),
        layout={
            "x": bounds.get("x", 0),
            "y": bounds.get("y", 0),
            "width": bounds.get("width", 0),
            "height": bounds.get("height", 0),
        },
        children=children,
        text=text,
        meta={"visible": node.get("visible", True)},
    )
