"""
Recursive executor for the Multi-AI Sequence DSL.

This module executes a validated Flow AST.

Execution semantics:

    CommandNode
        Execute one command using the current AgentSession.

    SequenceNode
        Execute child nodes from left to right using the same session.
        Stop immediately when a child fails.

    ParallelNode
        Create one independent child AgentSession per branch.
        Execute branches concurrently.
        Wait for all branches to finish.
        The ParallelNode succeeds only when every branch succeeds.

Important:

    This executor controls execution topology only.

    It does not propagate:
        - Agent output
        - Artifact data
        - conversation history
        - branch state

    across fork/join boundaries.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Callable

from .config import logger
from .flow_ast import (
    CommandNode,
    FlowNode,
    ParallelNode,
    SequenceNode,
)

if TYPE_CHECKING:
    from .session import AgentSession


DispatchFunction = Callable[
    [list[str], "AgentSession"],
    bool,
]


class FlowExecutionError(RuntimeError):
    """
    Raised when the Flow executor encounters an unsupported AST structure.
    """


def execute_flow(
    root: FlowNode,
    session: "AgentSession",
    *,
    dispatch: DispatchFunction | None = None,
) -> bool:
    """
    Execute a validated Flow AST.

    Args:
        root:
            Root Flow AST node.

        session:
            Parent AgentSession used for sequential execution.

        dispatch:
            Optional command dispatcher.

            Primarily useful for testing. When omitted,
            multi_ai_cli.handlers.dispatch_command is loaded lazily.

    Returns:
        bool:
            True when the complete Flow succeeds.
            False when any node fails.
    """
    if dispatch is None:
        # Lazy import avoids a module-level circular dependency:
        #
        # handlers
        #   -> flow_executor
        #   -> handlers.dispatch_command
        #
        from .handlers import dispatch_command

        dispatch = dispatch_command

    return execute_node(
        root,
        session,
        dispatch=dispatch,
    )


def execute_node(
    node: FlowNode,
    session: "AgentSession",
    *,
    dispatch: DispatchFunction,
) -> bool:
    """
    Recursively execute one Flow AST node.
    """
    if isinstance(node, CommandNode):
        return _execute_command(
            node,
            session,
            dispatch=dispatch,
        )

    if isinstance(node, SequenceNode):
        return _execute_sequence(
            node,
            session,
            dispatch=dispatch,
        )

    if isinstance(node, ParallelNode):
        return _execute_parallel(
            node,
            session,
            dispatch=dispatch,
        )

    raise FlowExecutionError(
        f"Unsupported Flow node type: {type(node).__name__}"
    )


def _execute_command(
    node: CommandNode,
    session: "AgentSession",
    *,
    dispatch: DispatchFunction,
) -> bool:
    """
    Execute one command using the current session.
    """
    try:
        return bool(
            dispatch(
                node.tokens,
                session,
            )
        )

    except Exception as exc:
        logger.error(
            "Flow command failed: %s: %s",
            node.tokens,
            exc,
        )
        return False


def _execute_sequence(
    node: SequenceNode,
    session: "AgentSession",
    *,
    dispatch: DispatchFunction,
) -> bool:
    """
    Execute SequenceNode children from left to right.

    The same AgentSession is reused for every child in the sequence.
    """
    for child in node.children:
        success = execute_node(
            child,
            session,
            dispatch=dispatch,
        )

        if not success:
            return False

    return True


def _execute_parallel(
    node: ParallelNode,
    session: "AgentSession",
    *,
    dispatch: DispatchFunction,
) -> bool:
    """
    Execute all ParallelNode branches concurrently.

    Each branch receives exactly one independent child session.

    A sequence inside one branch therefore shares the same child session:

        [
          ( @gpt -> @gemini )
          ||
          @grok
        ]

    becomes conceptually:

        child_session_1:
            @gpt
              ->
            @gemini

        child_session_2:
            @grok

    Nested ParallelNodes create further child sessions beneath the
    branch session currently executing them.
    """
    if not node.branches:
        return False

    results: dict[int, bool] = {}

    with ThreadPoolExecutor(
        max_workers=len(node.branches)
    ) as executor:

        future_to_branch: dict[object, int] = {}

        for branch_index, branch in enumerate(
            node.branches,
            1,
        ):
            # Step 7:
            # one independent child session per Parallel branch.
            child_session = session.create_child_session()

            future = executor.submit(
                execute_node,
                branch,
                child_session,
                dispatch=dispatch,
            )

            future_to_branch[future] = branch_index

        for future in as_completed(future_to_branch):
            branch_index = future_to_branch[future]

            try:
                results[branch_index] = bool(
                    future.result()
                )

            except Exception as exc:
                logger.error(
                    "Parallel branch %s failed: %s",
                    branch_index,
                    exc,
                )

                results[branch_index] = False

    return (
        len(results) == len(node.branches)
        and all(results.values())
    )