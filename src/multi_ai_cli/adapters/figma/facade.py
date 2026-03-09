"""
CLI facade for the Figma adapter.

Parses command-line tokens, builds request objects, delegates to the
adapter, and handles output.  Kept deliberately thin — all business
logic lives in ``adapter.py`` and the backends.
"""

from __future__ import annotations

import json
import os

from ...config import config, logger
from ...utils import safe_print, secure_resolve_path
from .adapter import FigmaAdapter
from .backends.plugin_bridge_backend import PluginBridgeBackend
from .backends.rest_backend import RestBackend
from .models import FigmaError, FigmaPullRequest, FigmaPushRequest

# ------------------------------------------------------------------
# Adapter construction
# ------------------------------------------------------------------


def _build_adapter(require_token: bool) -> FigmaAdapter:
    """Assembles a ``FigmaAdapter`` from the current configuration.

    Args:
        require_token: When *True* the call raises ``FigmaError`` if
            ``FIGMA_ACCESS_TOKEN`` is missing.  ``@figma.push`` passes
            *False* because it only writes local files.
    """
    token = (
        os.getenv("FIGMA_ACCESS_TOKEN")
        or config.get("API_KEYS", "figma_access_token", fallback="").strip()
    )

    pull_backend: RestBackend | None = None
    if token:
        pull_backend = RestBackend(access_token=token)
    elif require_token:
        raise FigmaError(
            "@figma.pull: FIGMA_ACCESS_TOKEN is not set. "
            "Set it as an environment variable or in "
            "multi_ai_cli.ini [API_KEYS]."
        )

    handoff_dir = config.get("FIGMA", "handoff_dir", fallback="work_data/figma_handoff")
    push_backend = PluginBridgeBackend(handoff_dir=handoff_dir)

    return FigmaAdapter(
        pull_backend=pull_backend,
        push_backend=push_backend,
    )


# ------------------------------------------------------------------
# Public handlers (called from dispatch_command)
# ------------------------------------------------------------------


def handle_figma_pull(parts: list[str]) -> bool:
    """Entry point for ``@figma.pull``.

    Parses CLI tokens, calls the adapter, and writes or prints the
    result.  Returns *True* on success, *False* on any error.
    """
    try:
        request, write_file = _parse_pull_args(parts)
        adapter = _build_adapter(require_token=True)
        response = adapter.pull(request)

        output = response.to_dict()

        if write_file:
            out_path = secure_resolve_path(write_file, "data", config=config)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            safe_print(f"[*] @figma.pull: Result saved to '{write_file}'")
        else:
            safe_print("\n--- @figma.pull ---")
            safe_print(json.dumps(output, indent=2, ensure_ascii=False))
            safe_print("--- end ---\n")

        return True

    except FigmaError as e:
        safe_print(f"[!] {e}")
        logger.error(f"figma.pull error: {e}")
        return False
    except Exception as e:
        safe_print(f"[!] @figma.pull: Unexpected error: {e}")
        logger.error(f"figma.pull unexpected error: {e}")
        return False


def handle_figma_push(parts: list[str]) -> bool:
    """Entry point for ``@figma.push``.

    Parses CLI tokens, reads the input file, calls the adapter, and
    optionally saves the operation summary.  Returns *True* on success.
    """
    try:
        request, write_file, content = _parse_push_args(parts)
        adapter = _build_adapter(require_token=False)
        response = adapter.push(request, content)

        safe_print(f"[*] @figma.push: {response.message}")

        if write_file:
            out_path = secure_resolve_path(write_file, "data", config=config)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(response.to_dict(), f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            safe_print(f"[*] @figma.push: Operation summary saved to '{write_file}'")

        return response.success

    except FigmaError as e:
        safe_print(f"[!] {e}")
        logger.error(f"figma.push error: {e}")
        return False
    except Exception as e:
        safe_print(f"[!] @figma.push: Unexpected error: {e}")
        logger.error(f"figma.push unexpected error: {e}")
        return False


# ------------------------------------------------------------------
# Argument parsers
# ------------------------------------------------------------------


def _parse_pull_args(
    parts: list[str],
) -> tuple[FigmaPullRequest, str | None]:
    """Tokenises ``@figma.pull`` arguments.

    Raises:
        FigmaError: If ``--file`` is missing or ``--node`` and
            ``--page`` are specified together.
    """
    file_key: str | None = None
    node_id: str | None = None
    page: str | None = None
    depth: int | None = None
    output_format: str = "normalized-json"
    write_file: str | None = None

    i = 1
    while i < len(parts):
        token = parts[i]
        if token == "--file" and i + 1 < len(parts):
            file_key = parts[i + 1]
            i += 2
            continue
        if token == "--node" and i + 1 < len(parts):
            node_id = parts[i + 1]
            i += 2
            continue
        if token == "--page" and i + 1 < len(parts):
            page = parts[i + 1]
            i += 2
            continue
        if token == "--depth" and i + 1 < len(parts):
            depth = int(parts[i + 1])
            i += 2
            continue
        if token == "--output-format" and i + 1 < len(parts):
            output_format = parts[i + 1]
            i += 2
            continue
        if token in ("-w", "--write") and i + 1 < len(parts):
            write_file = parts[i + 1]
            i += 2
            continue
        i += 1

    if not file_key:
        raise FigmaError("@figma.pull: --file <file_key> is required.")

    if node_id and page:
        raise FigmaError(
            "@figma.pull: --node and --page cannot be used together. "
            "Specify one or the other."
        )

    request = FigmaPullRequest(
        file_key=file_key,
        node_id=node_id,
        page=page,
        depth=depth,
        output_format=output_format,
    )
    return request, write_file


def _parse_push_args(
    parts: list[str],
) -> tuple[FigmaPushRequest, str | None, str]:
    """Tokenises ``@figma.push`` arguments and reads the input file.

    Raises:
        FigmaError: If ``-r`` is missing.
    """
    input_file: str | None = None
    file_key: str | None = None
    page: str | None = None
    frame: str | None = None
    input_format: str | None = None
    write_file: str | None = None

    i = 1
    while i < len(parts):
        token = parts[i]
        if token in ("-r", "--read") and i + 1 < len(parts):
            input_file = parts[i + 1]
            i += 2
            continue
        if token == "--file" and i + 1 < len(parts):
            file_key = parts[i + 1]
            i += 2
            continue
        if token == "--page" and i + 1 < len(parts):
            page = parts[i + 1]
            i += 2
            continue
        if token == "--frame" and i + 1 < len(parts):
            frame = parts[i + 1]
            i += 2
            continue
        if token == "--input-format" and i + 1 < len(parts):
            input_format = parts[i + 1]
            i += 2
            continue
        if token in ("-w", "--write") and i + 1 < len(parts):
            write_file = parts[i + 1]
            i += 2
            continue
        i += 1

    if not input_file:
        raise FigmaError("@figma.push: -r <file> is required.")

    filepath = secure_resolve_path(input_file, "data", config=config)
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    request = FigmaPushRequest(
        input_file=input_file,
        file_key=file_key,
        page=page,
        frame=frame,
        input_format=input_format,
    )
    return request, write_file, content
