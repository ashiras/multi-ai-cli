"""
Recursive executor for the Multi-AI Sequence DSL.

Execution semantics:

    CommandNode
        Execute one command using the current AgentSession.

    SequenceNode
        Execute child nodes from left to right using the same session
        and the same FlowExecutionContext.

    ParallelNode
        Create one independent child AgentSession per branch.
        Add one level to the Branch Path.
        Execute all branches concurrently.
        Wait for all branches to finish.

The executor controls execution topology only.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from typing import TYPE_CHECKING

from .config import logger
from .flow_ast import (
    CommandNode,
    FlowNode,
    ParallelNode,
    SequenceNode,
)
from .flow_context import (
    FlowExecutionContext,
    bind_flow_execution_context,
    get_flow_execution_context,
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
    session: AgentSession,
    *,
    dispatch: DispatchFunction | None = None,
) -> bool:
    """
    Execute a validated Flow AST.

    If execution starts from inside another Flow branch, the currently
    active FlowExecutionContext is inherited.
    """
    if dispatch is None:
        # Lazy import avoids:
        #
        # handlers
        #   -> flow_executor
        #   -> handlers.dispatch_command
        #
        from .handlers import dispatch_command

        dispatch = dispatch_command

    root_context = get_flow_execution_context()

    return execute_node(
        root,
        session,
        dispatch=dispatch,
        context=root_context,
    )


def execute_node(
    node: FlowNode,
    session: AgentSession,
    *,
    dispatch: DispatchFunction,
    context: FlowExecutionContext,
) -> bool:
    """
    Recursively execute one Flow AST node.
    """
    if isinstance(node, CommandNode):
        return _execute_command(
            node,
            session,
            dispatch=dispatch,
            context=context,
        )

    if isinstance(node, SequenceNode):
        return _execute_sequence(
            node,
            session,
            dispatch=dispatch,
            context=context,
        )

    if isinstance(node, ParallelNode):
        return _execute_parallel(
            node,
            session,
            dispatch=dispatch,
            context=context,
        )

    raise FlowExecutionError(f"Unsupported Flow node type: {type(node).__name__}")


def _execute_command(
    node: CommandNode,
    session: AgentSession,
    *,
    dispatch: DispatchFunction,
    context: FlowExecutionContext,
) -> bool:
    """
    Execute one command using the current session and Branch Path.
    """
    with bind_flow_execution_context(context):
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
    session: AgentSession,
    *,
    dispatch: DispatchFunction,
    context: FlowExecutionContext,
) -> bool:
    """
    Execute SequenceNode children from left to right.

    Sequence execution does not change the Branch Path.
    """
    for child in node.children:
        success = execute_node(
            child,
            session,
            dispatch=dispatch,
            context=context,
        )

        if not success:
            return False

    return True


def _execute_parallel(
    node: ParallelNode,
    session: AgentSession,
    *,
    dispatch: DispatchFunction,
    context: FlowExecutionContext,
) -> bool:
    """
    Execute all ParallelNode branches concurrently.

    Each branch receives:

        - one independent child AgentSession
        - one child FlowExecutionContext

    Example:
        root
          |
          +-- branch 1 -> B1
          |
          +-- branch 2 -> B2

    Nested:

        B1
          |
          +-- branch 1 -> B1.1
          |
          +-- branch 2 -> B1.2
    """
    if not node.branches:
        return False

    results: dict[int, bool] = {}

    with ThreadPoolExecutor(max_workers=len(node.branches)) as executor:
        future_to_branch = {}

        for branch_index, branch in enumerate(
            node.branches,
            1,
        ):
            child_session = session.create_child_session()

            branch_context = context.child_branch(branch_index)

            future = executor.submit(
                execute_node,
                branch,
                child_session,
                dispatch=dispatch,
                context=branch_context,
            )

            future_to_branch[future] = branch_index

        for future in as_completed(future_to_branch):
            branch_index = future_to_branch[future]

            try:
                results[branch_index] = bool(future.result())

            except Exception as exc:
                logger.error(
                    "Parallel branch %s failed: %s",
                    branch_index,
                    exc,
                )

                results[branch_index] = False

    return len(results) == len(node.branches) and all(results.values())
