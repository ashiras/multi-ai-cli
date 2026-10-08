import pytest

from multi_ai_cli.flow_context import (
    FlowExecutionContext,
    bind_flow_execution_context,
    get_flow_execution_context,
)


def test_flow_execution_context_context_vars() -> None:
    # Default context should be root (empty path)
    ctx = get_flow_execution_context()
    assert ctx.branch_path == ()

    # Test binding a new context
    custom_ctx = FlowExecutionContext(branch_path=(1, 5))
    with bind_flow_execution_context(custom_ctx):
        assert get_flow_execution_context() == custom_ctx

    # Should revert to default after exiting context
    assert get_flow_execution_context().branch_path == ()


def test_flow_execution_context_path_derivation() -> None:
    # Root context
    ctx = FlowExecutionContext()
    assert ctx.branch_path == ()
    assert ctx.branch_label is None

    # First level
    ctx1 = ctx.child_branch(1)
    assert ctx1.branch_path == (1,)
    assert ctx1.branch_label == "B1"

    # Second level
    ctx1_2 = ctx1.child_branch(2)
    assert ctx1_2.branch_path == (1, 2)
    assert ctx1_2.branch_label == "B1.2"

    # Deep nesting
    ctx_deep = ctx1_2.child_branch(3).child_branch(4)
    assert ctx_deep.branch_path == (1, 2, 3, 4)
    assert ctx_deep.branch_label == "B1.2.3.4"


def test_flow_execution_context_invalid_branch_index() -> None:
    ctx = FlowExecutionContext()
    with pytest.raises(ValueError, match="branch_index must be >= 1"):
        ctx.child_branch(0)
    with pytest.raises(ValueError, match="branch_index must be >= 1"):
        ctx.child_branch(-1)
