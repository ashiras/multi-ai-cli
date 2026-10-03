from types import SimpleNamespace

import multi_ai_cli.handlers as handlers
from multi_ai_cli.flow_context import (
    FlowExecutionContext,
    bind_flow_execution_context,
)


class FakeEngine:
    name = "@gpt"

    def call(
        self,
        prompt: str,
    ) -> str:
        return "Hello from GPT"


class FakeSession:
    def get_agent(
        self,
        _agent_key: str,
    ):
        return FakeEngine()


def test_ai_output_contains_branch_label(
    monkeypatch,
    capsys,
) -> None:

    parsed = SimpleNamespace(
        use_editor=False,
        write_file=None,
        write_mode="raw",
    )

    monkeypatch.setattr(
        handlers,
        "parse_cli_input",
        lambda parts: parsed,
    )

    monkeypatch.setattr(
        handlers,
        "build_ai_prompt",
        lambda parsed, editor_content: "hello",
    )

    # Keep test output readable.
    monkeypatch.setattr(
        handlers,
        "clear_thinking_line",
        lambda: None,
    )

    context = FlowExecutionContext(branch_path=(1, 2))

    with bind_flow_execution_context(context):
        result = handlers.handle_ai_interaction(
            ["@gpt", "hello"],
            FakeSession(),
        )

    assert result is True

    output = capsys.readouterr().out

    assert "[B1.2] @gpt is thinking..." in output

    assert "--- [B1.2] @gpt ---" in output

    assert "Hello from GPT" in output
