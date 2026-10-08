import threading

from multi_ai_cli.flow_executor import execute_flow
from multi_ai_cli.flow_parser import parse_flow


class FakeSession:
    """
    Minimal AgentSession replacement for executor tests.

    Child session IDs preserve hierarchy:

        root
        root.1
        root.2
        root.1.1
        root.1.2
    """

    def __init__(
        self,
        name: str = "root",
    ) -> None:
        self.name = name
        self._child_count = 0
        self._lock = threading.Lock()

    def create_child_session(self) -> "FakeSession":
        with self._lock:
            self._child_count += 1
            child_number = self._child_count

        return FakeSession(f"{self.name}.{child_number}")


class RecordingDispatcher:
    """
    Thread-safe fake dispatcher.
    """

    def __init__(
        self,
        failures: set[str] | None = None,
    ) -> None:
        self.failures = failures or set()
        self.calls: list[tuple[tuple[str, ...], str]] = []
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

        command = tokens[0]

        return command not in self.failures


def test_sequence_reuses_parent_session() -> None:
    ast = parse_flow("@gpt -> @gemini -> @claude")

    session = FakeSession()
    dispatch = RecordingDispatcher()

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    assert dispatch.calls == [
        (("@gpt",), "root"),
        (("@gemini",), "root"),
        (("@claude",), "root"),
    ]


def test_sequence_stops_on_failure() -> None:
    ast = parse_flow("@gpt -> @gemini -> @claude")

    session = FakeSession()

    dispatch = RecordingDispatcher(failures={"@gemini"})

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is False

    assert dispatch.calls == [
        (("@gpt",), "root"),
        (("@gemini",), "root"),
    ]


def test_parallel_uses_one_child_session_per_branch() -> None:
    ast = parse_flow("[ @gpt || @gemini ]")

    session = FakeSession()
    dispatch = RecordingDispatcher()

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    calls = set(dispatch.calls)

    assert calls == {
        (("@gpt",), "root.1"),
        (("@gemini",), "root.2"),
    }


def test_sequence_branch_reuses_same_child_session() -> None:
    ast = parse_flow("[ ( @gpt -> @gemini ) || @grok ]")

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
        ("@gpt",),
        "root.1",
    ) in calls

    assert (
        ("@gemini",),
        "root.1",
    ) in calls

    assert (
        ("@grok",),
        "root.2",
    ) in calls


def test_join_continues_on_parent_session() -> None:
    ast = parse_flow("[ ( @gpt -> @gemini ) || @grok ] -> @claude")

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
        ("@gpt",),
        "root.1",
    ) in calls

    assert (
        ("@gemini",),
        "root.1",
    ) in calls

    assert (
        ("@grok",),
        "root.2",
    ) in calls

    # After join, execution returns to the parent session.
    assert (
        ("@claude",),
        "root",
    ) in calls


def test_parallel_fails_if_one_branch_fails() -> None:
    ast = parse_flow("[ @gpt || @fail ]")

    session = FakeSession()
    # @fail is not a command, it will return False if configured in failures
    dispatch = RecordingDispatcher(failures={"@fail"})

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is False


def test_sequence_skips_after_parallel_failure() -> None:
    # Sequence: Parallel node (one fails) -> @final_command
    ast = parse_flow("[ @gpt || @fail ] -> @final_command")

    session = FakeSession()
    dispatch = RecordingDispatcher(failures={"@fail"})

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is False

    # @final_command should not have been called because the sequence stopped
    assert (
        ("@final_command",),
        "root",
    ) not in dispatch.calls


def test_nested_parallel_creates_nested_child_sessions() -> None:
    ast = parse_flow(
        """
        [
          (
            @gpt
            ->
            [ @gemini || @claude ]
          )
          ||
          @grok
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

    # Outer branch 1
    assert (
        ("@gpt",),
        "root.1",
    ) in calls

    # Nested parallel under branch 1
    assert (
        ("@gemini",),
        "root.1.1",
    ) in calls

    assert (
        ("@claude",),
        "root.1.2",
    ) in calls

    # Outer branch 2
    assert (
        ("@grok",),
        "root.2",
    ) in calls


def test_parallel_failure_stops_sequence_after_join() -> None:
    ast = parse_flow(
        """
        [
          @gpt
          ||
          @gemini
        ]
        ->
        @claude
        """
    )

    session = FakeSession()

    dispatch = RecordingDispatcher(failures={"@gemini"})

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is False

    commands = {tokens[0] for tokens, _session_name in dispatch.calls}

    assert "@gpt" in commands
    assert "@gemini" in commands

    # Join failed, so the following sequential node must not run.
    assert "@claude" not in commands


def test_branch_path_tracks_nested_parallel_and_join() -> None:
    from multi_ai_cli.flow_context import (
        get_flow_execution_context,
    )

    ast = parse_flow(
        """
        [
          (
            @gpt outer-b1
            ->
            [
              @gemini nested-b1
              ||
              @claude nested-b2
            ]
            ->
            @local after-nested
          )
          ||
          @grok outer-b2
        ]
        ->
        @gpt after-outer
        """
    )

    session = FakeSession()

    calls = []
    lock = threading.Lock()

    def dispatch(
        tokens,
        _session,
    ):
        context = get_flow_execution_context()

        with lock:
            calls.append(
                (
                    tuple(tokens),
                    context.branch_label,
                )
            )

        return True

    result = execute_flow(
        ast,
        session,
        dispatch=dispatch,
    )

    assert result is True

    assert set(calls) == {
        (
            ("@gpt", "outer-b1"),
            "B1",
        ),
        (
            ("@gemini", "nested-b1"),
            "B1.1",
        ),
        (
            ("@claude", "nested-b2"),
            "B1.2",
        ),
        (
            ("@local", "after-nested"),
            "B1",
        ),
        (
            ("@grok", "outer-b2"),
            "B2",
        ),
        (
            ("@gpt", "after-outer"),
            None,
        ),
    }
