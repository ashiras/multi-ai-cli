"""
Execution context for the Multi-AI Flow DSL.

The context carries the current Parallel Branch path.

Examples:
    root        -> None
    branch 1    -> B1
    branch 2    -> B2
    nested 1    -> B1.1
    nested 2    -> B1.2

Sequence execution does not change the branch path.
Only entering a Parallel branch adds one level.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlowExecutionContext:
    """
    Runtime context for one Flow execution path.
    """

    branch_path: tuple[int, ...] = ()

    @property
    def branch_label(self) -> str | None:
        """
        Return a human-readable branch label.

        Examples:
            ()      -> None
            (1,)    -> "B1"
            (2,)    -> "B2"
            (1, 2)  -> "B1.2"
        """
        if not self.branch_path:
            return None

        return "B" + ".".join(str(index) for index in self.branch_path)

    def child_branch(
        self,
        branch_index: int,
    ) -> FlowExecutionContext:
        """
        Create the context for a child Parallel branch.
        """
        if branch_index < 1:
            raise ValueError("branch_index must be >= 1")

        return FlowExecutionContext(
            branch_path=(
                *self.branch_path,
                branch_index,
            )
        )


_current_flow_context: ContextVar[FlowExecutionContext] = ContextVar(
    "multi_ai_flow_execution_context",
    default=FlowExecutionContext(),
)


def get_flow_execution_context() -> FlowExecutionContext:
    """
    Return the Flow execution context active in the current execution.
    """
    return _current_flow_context.get()


@contextmanager
def bind_flow_execution_context(
    context: FlowExecutionContext,
) -> Iterator[None]:
    """
    Temporarily bind a Flow execution context.

    ContextVar keeps concurrent branches isolated even when they are
    executing in different ThreadPoolExecutor workers.
    """
    token = _current_flow_context.set(context)

    try:
        yield
    finally:
        _current_flow_context.reset(token)
