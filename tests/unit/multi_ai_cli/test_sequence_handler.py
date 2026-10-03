import multi_ai_cli.handlers as handlers
from multi_ai_cli.flow_parser import FlowSyntaxError
from multi_ai_cli.flow_validator import FlowValidationError


def test_handle_sequence_returns_true_when_flow_succeeds(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        handlers,
        "open_editor_for_prompt",
        lambda: "@gpt hello!",
    )

    fake_ast = object()

    monkeypatch.setattr(
        handlers,
        "parse_flow",
        lambda text: fake_ast,
    )

    monkeypatch.setattr(
        handlers,
        "validate_flow",
        lambda ast: None,
    )

    monkeypatch.setattr(
        handlers,
        "execute_flow",
        lambda ast, session: True,
    )

    result = handlers.handle_sequence(
        ["@sequence", "-e"],
        object(),
    )

    assert result is True


def test_handle_sequence_returns_false_when_execution_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        handlers,
        "open_editor_for_prompt",
        lambda: "@gpt hello!",
    )

    fake_ast = object()

    monkeypatch.setattr(
        handlers,
        "parse_flow",
        lambda text: fake_ast,
    )

    monkeypatch.setattr(
        handlers,
        "validate_flow",
        lambda ast: None,
    )

    monkeypatch.setattr(
        handlers,
        "execute_flow",
        lambda ast, session: False,
    )

    result = handlers.handle_sequence(
        ["@sequence", "-e"],
        object(),
    )

    assert result is False


def test_handle_sequence_returns_false_on_syntax_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        handlers,
        "open_editor_for_prompt",
        lambda: "[ @gpt || ]",
    )

    def fail_parse(_text):
        raise FlowSyntaxError(
            "test syntax error",
            0,
        )

    monkeypatch.setattr(
        handlers,
        "parse_flow",
        fail_parse,
    )

    result = handlers.handle_sequence(
        ["@sequence", "-e"],
        object(),
    )

    assert result is False


def test_handle_sequence_returns_false_on_validation_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        handlers,
        "open_editor_for_prompt",
        lambda: "[ @gpt || @gpt ]",
    )

    fake_ast = object()

    monkeypatch.setattr(
        handlers,
        "parse_flow",
        lambda text: fake_ast,
    )

    def fail_validation(_ast):
        raise FlowValidationError("duplicate Agent")

    monkeypatch.setattr(
        handlers,
        "validate_flow",
        fail_validation,
    )

    result = handlers.handle_sequence(
        ["@sequence", "-e"],
        object(),
    )

    assert result is False


def test_sequence_dispatch_propagates_failure(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        handlers,
        "handle_sequence",
        lambda parts, session: False,
    )

    result = handlers.dispatch_command(
        ["@sequence", "-e"],
        object(),
    )

    assert result is False


def test_sequence_file_mode_returns_true(
    monkeypatch,
    tmp_path,
) -> None:
    flow_file = tmp_path / "test.seq"
    flow_file.write_text(
        "@gpt hello!",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        handlers,
        "secure_resolve_path",
        lambda filename, kind, config=None: flow_file,
    )

    fake_ast = object()

    monkeypatch.setattr(
        handlers,
        "parse_flow",
        lambda text: fake_ast,
    )

    monkeypatch.setattr(
        handlers,
        "validate_flow",
        lambda ast: None,
    )

    monkeypatch.setattr(
        handlers,
        "execute_flow",
        lambda ast, session: True,
    )

    result = handlers.handle_sequence(
        [
            "@sequence",
            "-f",
            "test.seq",
        ],
        object(),
    )

    assert result is True
