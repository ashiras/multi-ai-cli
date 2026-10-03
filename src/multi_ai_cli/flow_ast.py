"""
AST definitions for the Multi-AI Sequence DSL.

This module contains structure only.
It does not perform parsing, validation, or execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CommandNode:
    """
    A single executable Multi-AI command.

    Example:
        @gpt hello!
    """

    tokens: list[str]


@dataclass(slots=True)
class SequenceNode:
    """
    A sequence of nodes executed from left to right.

    Example:
        @gpt -> @gemini -> @claude
    """

    children: list[FlowNode] = field(default_factory=list)


@dataclass(slots=True)
class ParallelNode:
    """
    A fork/join structure.

    Each branch may be a CommandNode, SequenceNode,
    or another ParallelNode.

    Example:
        [ @gpt || @gemini ]

        [
          ( @gpt -> @gemini )
          ||
          @grok
        ]
    """

    branches: list[FlowNode] = field(default_factory=list)


type FlowNode = CommandNode | SequenceNode | ParallelNode
