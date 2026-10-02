"""
Issue 2 regression tests for AgentDefinition / AgentInstance / AgentSession isolation.

These tests do not call external APIs.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest

from multi_ai_cli.agent_factory import AgentFactory
from multi_ai_cli.registry import AgentDefinition, AgentRegistry
from multi_ai_cli.session import AgentSession


@pytest.fixture
def reviewer_definition() -> AgentDefinition:
    return AgentDefinition(
        agent_key="reviewer",
        adapter="openai-compatible",
        server="http://localhost:11434/v1",
        engine="dummy-model",
        api_key_ref=None,
        role="review",
        max_output_tokens=1024,
    )


@pytest.fixture
def registry(reviewer_definition: AgentDefinition) -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(reviewer_definition)
    return reg


@dataclass
class DummyEngine:
    name: str

    def __post_init__(self) -> None:
        self.history: list[dict[str, str]] = []
        self.system_prompt = ""
        self.filter_mode = False

    def call(self, prompt: str) -> str:
        answer = f"answer:{prompt}"
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": answer})
        return answer

    def scrub(self) -> None:
        self.history = []

    def load_persona(self, prompt_text: str, filename: str = "") -> None:
        self.system_prompt = prompt_text
        self.history = []


class DummyFactory:
    def create(self, agent_def: AgentDefinition) -> DummyEngine:
        return DummyEngine(name=agent_def.display_label)


def test_factory_creates_independent_instances(
    reviewer_definition: AgentDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AgentFactory.create() must return a fresh runtime instance."""
    factory = AgentFactory()

    if hasattr(factory, "_get_or_create_client"):
        monkeypatch.setattr(
            factory,
            "_get_or_create_client",
            lambda _agent_def: object(),
        )
    elif hasattr(factory, "_get_or_create_openai_client"):
        monkeypatch.setattr(
            factory,
            "_get_or_create_openai_client",
            lambda _agent_def: object(),
        )

    agent_a = factory.create(reviewer_definition)
    agent_b = factory.create(reviewer_definition)

    assert agent_a is not agent_b
    assert agent_a.history is not agent_b.history

    agent_a.history.append({"role": "user", "content": "A_ONLY"})

    assert agent_a.history
    assert agent_b.history == []


def test_same_session_reuses_same_agent(registry: AgentRegistry) -> None:
    """The same session + same agent key must reuse one runtime instance."""
    session = AgentSession(registry, DummyFactory())

    agent_a = session.get_agent("reviewer")
    agent_b = session.get_agent("reviewer")

    assert agent_a is agent_b


def test_different_sessions_get_independent_agents(
    registry: AgentRegistry,
) -> None:
    """Different sessions must never share runtime state."""
    factory = DummyFactory()

    session_a = AgentSession(registry, factory)
    session_b = AgentSession(registry, factory)

    agent_a = session_a.get_agent("reviewer")
    agent_b = session_b.get_agent("reviewer")

    assert agent_a is not agent_b
    assert agent_a.history is not agent_b.history

    agent_a.call("A_ONLY")

    assert any("A_ONLY" in item["content"] for item in agent_a.history)
    assert not any("A_ONLY" in item["content"] for item in agent_b.history)


def test_same_agent_name_can_run_in_parallel_without_history_leakage(
    registry: AgentRegistry,
) -> None:
    """
    Main Issue 2 regression test:
    the same logical agent runs concurrently in isolated child sessions.
    """
    factory = DummyFactory()
    prompts = ["A_ONLY", "B_ONLY", "C_ONLY"]

    def run_task(prompt: str):
        child_session = AgentSession(registry, factory)
        engine = child_session.get_agent("reviewer")
        result = engine.call(prompt)
        return result, engine

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(run_task, prompts))

    engines = [engine for _, engine in results]

    assert len({id(engine) for engine in engines}) == 3

    for expected_prompt, (_, engine) in zip(prompts, results):
        contents = [item["content"] for item in engine.history]

        assert expected_prompt in contents

        for other_prompt in prompts:
            if other_prompt != expected_prompt:
                assert other_prompt not in contents


def test_scrub_does_not_affect_other_session(
    registry: AgentRegistry,
) -> None:
    """Scrubbing one session must not clear another session's history."""
    factory = DummyFactory()

    session_a = AgentSession(registry, factory)
    session_b = AgentSession(registry, factory)

    agent_a = session_a.get_agent("reviewer")
    agent_b = session_b.get_agent("reviewer")

    agent_a.call("AAA")
    agent_b.call("BBB")

    if hasattr(session_a, "scrub"):
        session_a.scrub("reviewer")
    else:
        agent_a.scrub()

    assert agent_a.history == []
    assert any("BBB" in item["content"] for item in agent_b.history)


def test_persona_is_session_local(registry: AgentRegistry) -> None:
    """A persona/system prompt loaded in one session must not leak."""
    factory = DummyFactory()

    session_a = AgentSession(registry, factory)
    session_b = AgentSession(registry, factory)

    agent_a = session_a.get_agent("reviewer")
    agent_b = session_b.get_agent("reviewer")

    agent_a.load_persona("PERSONA_A", "persona-a.md")

    assert agent_a.system_prompt == "PERSONA_A"
    assert agent_b.system_prompt == ""


def test_runtime_flags_are_instance_local(registry: AgentRegistry) -> None:
    """Runtime flags such as filter_mode must be instance-local."""
    factory = DummyFactory()

    session_a = AgentSession(registry, factory)
    session_b = AgentSession(registry, factory)

    agent_a = session_a.get_agent("reviewer")
    agent_b = session_b.get_agent("reviewer")

    agent_a.filter_mode = True

    assert agent_a.filter_mode is True
    assert agent_b.filter_mode is False
