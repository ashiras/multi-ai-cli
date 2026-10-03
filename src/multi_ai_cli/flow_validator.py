"""
Semantic validation for the Multi-AI Sequence DSL.

The parser is responsible only for syntax and AST construction.

This module validates execution constraints that cannot be determined
from grammar alone, including:

- unknown commands
- @pause inside parallel execution
- duplicate Agent aliases across parallel branches

It does not execute Flow nodes.
"""

from __future__ import annotations

from .flow_ast import (
    CommandNode,
    FlowNode,
    ParallelNode,
    SequenceNode,
)
from .parsers import BUILTIN_COMMANDS, get_valid_commands


class FlowValidationError(ValueError):
    """
    Raised when a syntactically valid Flow violates semantic rules.
    """


def validate_flow(root: FlowNode) -> None:
    """
    Validate a parsed Flow AST.

    Validation rules:

    1. Every command must be registered.
    2. @pause may not appear anywhere inside a Parallel subtree.
    3. The same Agent alias may not appear in different branches
       of the same Parallel node.

    Sequential reuse of the same Agent is allowed.

    Args:
        root: Root Flow AST node.

    Raises:
        FlowValidationError:
            If any semantic rule is violated.
    """
    valid_commands = get_valid_commands()

    # Built-in commands are execution/control commands rather than Agents.
    # Duplicate-Agent validation applies only to Agent aliases.
    agent_commands = valid_commands - BUILTIN_COMMANDS

    _validate_node(
        root,
        valid_commands=valid_commands,
        agent_commands=agent_commands,
        inside_parallel=False,
    )


def _validate_node(
    node: FlowNode,
    *,
    valid_commands: set[str],
    agent_commands: set[str],
    inside_parallel: bool,
) -> None:
    """
    Recursively validate one AST node.
    """

    if isinstance(node, CommandNode):
        _validate_command(
            node,
            valid_commands=valid_commands,
            inside_parallel=inside_parallel,
        )
        return

    if isinstance(node, SequenceNode):
        for child in node.children:
            _validate_node(
                child,
                valid_commands=valid_commands,
                agent_commands=agent_commands,
                inside_parallel=inside_parallel,
            )
        return

    if isinstance(node, ParallelNode):
        _validate_parallel(
            node,
            valid_commands=valid_commands,
            agent_commands=agent_commands,
        )
        return

    raise FlowValidationError(
        f"Unsupported Flow node type: {type(node).__name__}"
    )


def _validate_command(
    node: CommandNode,
    *,
    valid_commands: set[str],
    inside_parallel: bool,
) -> None:
    """
    Validate a CommandNode.
    """
    if not node.tokens:
        raise FlowValidationError(
            "Command node contains no tokens."
        )

    command = node.tokens[0]
    command_key = _normalize_command_key(command)

    if command_key not in valid_commands:
        raise FlowValidationError(
            f"Unknown command: @{command_key}"
        )

    if inside_parallel and command_key == "pause":
        raise FlowValidationError(
            "@pause cannot be used inside a parallel block."
        )


def _validate_parallel(
    node: ParallelNode,
    *,
    valid_commands: set[str],
    agent_commands: set[str],
) -> None:
    """
    Validate a ParallelNode and all of its branches.

    Each branch is independently validated as a Parallel subtree.

    After validation, Agent usage is collected for each branch.
    Agent aliases may not overlap between sibling branches.
    """
    if len(node.branches) < 2:
        raise FlowValidationError(
            "Parallel block requires at least two branches."
        )

    # First validate each branch recursively.
    #
    # inside_parallel=True propagates through the entire branch subtree.
    # This automatically rejects @pause at any nesting depth.
    for branch in node.branches:
        _validate_node(
            branch,
            valid_commands=valid_commands,
            agent_commands=agent_commands,
            inside_parallel=True,
        )

    # Collect every Agent that may execute inside each branch.
    branch_agents = [
        _collect_agent_keys(
            branch,
            agent_commands=agent_commands,
        )
        for branch in node.branches
    ]

    # Compare sibling branches.
    #
    # Repeated use of an Agent inside one sequential branch is allowed.
    # Reuse across separate parallel branches is not.
    for left_index in range(len(branch_agents)):
        for right_index in range(
            left_index + 1,
            len(branch_agents),
        ):
            duplicates = (
                branch_agents[left_index]
                & branch_agents[right_index]
            )

            if duplicates:
                duplicate_list = ", ".join(
                    f"@{name}"
                    for name in sorted(duplicates)
                )

                raise FlowValidationError(
                    "Parallel branches contain duplicate "
                    f"Agent alias(es): {duplicate_list}"
                )


def _collect_agent_keys(
    node: FlowNode,
    *,
    agent_commands: set[str],
) -> set[str]:
    """
    Collect Agent aliases used anywhere below a Flow node.

    Built-in commands such as @pause, @sh, @efficient, etc.
    are intentionally excluded.
    """

    if isinstance(node, CommandNode):
        if not node.tokens:
            return set()

        command_key = _normalize_command_key(
            node.tokens[0]
        )

        if command_key in agent_commands:
            return {command_key}

        return set()

    if isinstance(node, SequenceNode):
        agents: set[str] = set()

        for child in node.children:
            agents.update(
                _collect_agent_keys(
                    child,
                    agent_commands=agent_commands,
                )
            )

        return agents

    if isinstance(node, ParallelNode):
        agents: set[str] = set()

        for branch in node.branches:
            agents.update(
                _collect_agent_keys(
                    branch,
                    agent_commands=agent_commands,
                )
            )

        return agents

    raise FlowValidationError(
        f"Unsupported Flow node type: {type(node).__name__}"
    )


def _normalize_command_key(command: str) -> str:
    """
    Convert '@gpt' or 'gpt' to canonical Agent/command key 'gpt'.
    """
    return command.lower().lstrip("@")