import threading
from unittest.mock import patch

import pytest

from multi_ai_cli.flow_executor import execute_flow
from multi_ai_cli.flow_parser import parse_flow
from multi_ai_cli.flow_validator import (
    FlowValidationError,
    validate_flow,
)
from multi_ai_cli.parsers import BUILTIN_COMMANDS


AGENTS = {
    "gpt",
    "gemini",
    "claude",
    "grok",
    "local",
}

VALID_COMMANDS = (
    BUILTIN_COMMANDS
    | AGENTS
)


class FakeSession:

    def __init__(
        self,
        name: str = "root",
    ) -> None:
        self.name = name
        self._child_count = 0
        self._lock = threading.Lock()

    def create_child_session(
        self,
    ) -> "FakeSession":
        with self._lock:
            self._child_count += 1

            child_number = (
                self._child_count
            )

        return FakeSession(
            f"{self.name}.{child_number}"
        )


class RecordingDispatcher:

    def __init__(
        self,
        failures: set[str] | None = None,
    ) -> None:
        self.failures = failures or set()

        self.calls: list[
            tuple[tuple[str, ...], str]
        ] = []

        self._lock = threading.Lock()

    def __call__(
        self,
        tokens: list[str],
        session: FakeSession,
    ) -> bool:

        with self._lock:
            self.calls.append(
                (
                    tuple(tokens),
                    session.name,
                )
            )

        return (
            tokens[0]
            not in self.failures
        )


def prepare_flow(text: str):
    ast = parse_flow(text)

    with patch(
        "multi_ai_cli.flow_validator.get_valid_commands",
        return_value=VALID_COMMANDS,
    ):
        validate_flow(ast)

    return ast


def test_legacy_sequence_pipeline() -> None:
    ast = prepare_flow(
        """
        @gpt hello!
        ->
        @gemini hello!
        ->
        @claude hello!
        """
    )

    session = FakeSession()
    dispatch = RecordingDispatcher()

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    assert dispatch.calls == [
        (
            ("@gpt", "hello!"),
            "root",
        ),
        (
            ("@gemini", "hello!"),
            "root",
        ),
        (
            ("@claude", "hello!"),
            "root",
        ),
    ]


def test_legacy_parallel_pipeline() -> None:
    ast = prepare_flow(
        """
        @gpt hello!
        ->
        [
          @gemini hello!
          ||
          @claude hello!
        ]
        """
    )

    session = FakeSession()
    dispatch = RecordingDispatcher()

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    calls = set(dispatch.calls)

    assert (
        ("@gpt", "hello!"),
        "root",
    ) in calls

    assert (
        ("@gemini", "hello!"),
        "root.1",
    ) in calls

    assert (
        ("@claude", "hello!"),
        "root.2",
    ) in calls


def test_nested_flow_pipeline() -> None:
    ast = prepare_flow(
        """
        [
          (
            @gpt hello!
            ->
            [
              @gemini hello!
              ||
              @claude hello!
            ]
          )
          ||
          (
            @grok hello!
            ->
            @local hello!
          )
        ]
        ->
        @grok hello-again!
        """
    )

    session = FakeSession()
    dispatch = RecordingDispatcher()

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    calls = set(dispatch.calls)

    assert (
        ("@gpt", "hello!"),
        "root.1",
    ) in calls

    assert (
        ("@gemini", "hello!"),
        "root.1.1",
    ) in calls

    assert (
        ("@claude", "hello!"),
        "root.1.2",
    ) in calls

    assert (
        ("@grok", "hello!"),
        "root.2",
    ) in calls

    assert (
        ("@local", "hello!"),
        "root.2",
    ) in calls

    # Join後はparent sessionへ戻る。
    assert (
        ("@grok", "hello-again!"),
        "root",
    ) in calls


def test_duplicate_agent_is_rejected_before_execution() -> None:
    ast = parse_flow(
        """
        [
          ( @gpt hello! -> @gemini hello! )
          ||
          ( @claude hello! -> @gpt hello! )
        ]
        """
    )

    with patch(
        "multi_ai_cli.flow_validator.get_valid_commands",
        return_value=VALID_COMMANDS,
    ):
        with pytest.raises(
            FlowValidationError,
            match="duplicate Agent",
        ):
            validate_flow(ast)


def test_pause_inside_parallel_is_rejected() -> None:
    ast = parse_flow(
        """
        [
          (
            @gpt hello!
            ->
            @pause
            ->
            @gemini hello!
          )
          ||
          @grok hello!
        ]
        """
    )

    with patch(
        "multi_ai_cli.flow_validator.get_valid_commands",
        return_value=VALID_COMMANDS,
    ):
        with pytest.raises(
            FlowValidationError,
            match="@pause cannot be used inside",
        ):
            validate_flow(ast)


def test_pause_after_join_is_valid_and_sequential() -> None:
    ast = prepare_flow(
        """
        [
          (
            @gpt branch-a
            ->
            @gemini branch-a
          )
          ||
          @grok branch-b
        ]
        ->
        @pause
        ->
        @gpt after-pause
        """
    )

    session = FakeSession()
    dispatch = RecordingDispatcher()

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    calls = dispatch.calls

    pause_index = calls.index(
        (
            ("@pause",),
            "root",
        )
    )

    final_index = calls.index(
        (
            (
                "@gpt",
                "after-pause",
            ),
            "root",
        )
    )

    branch_indexes = [
        calls.index(
            (
                ("@gpt", "branch-a"),
                "root.1",
            )
        ),
        calls.index(
            (
                ("@gemini", "branch-a"),
                "root.1",
            )
        ),
        calls.index(
            (
                ("@grok", "branch-b"),
                "root.2",
            )
        ),
    ]

    # @pauseはjoin後でなければならない。
    assert pause_index > max(
        branch_indexes
    )

    # そしてpause後に最後のGPT。
    assert final_index > pause_index


def test_parallel_failure_prevents_following_sequence() -> None:
    ast = prepare_flow(
        """
        [
          @gpt hello!
          ||
          @gemini hello!
        ]
        ->
        @claude should-not-run
        """
    )

    session = FakeSession()

    dispatch = RecordingDispatcher(
        failures={"@gemini"}
    )

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is False

    commands = [
        tokens[0]
        for tokens, _session
        in dispatch.calls
    ]

    assert "@gpt" in commands
    assert "@gemini" in commands

    assert "@claude" not in commands