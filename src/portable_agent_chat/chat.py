"""Chat session management for prompt execution and file integration."""

import multi_ai_cli.config as multi_ai_config
from multi_ai_cli.agent_factory import AgentFactory
from multi_ai_cli.registry import agent_registry
from multi_ai_cli.session import AgentSession
from portable_agent_chat.files import (
    ensure_new_file,
    read_file,
    resolve_read_paths,
    write_file,
    write_new_file,
)


def create_agent_session() -> AgentSession:
    """Create and return a configured agent session."""
    factory = AgentFactory()

    return AgentSession(
        registry=agent_registry,
        factory=factory,
        legacy_sdk_map=multi_ai_config.legacy_sdk_map,
    )


class ChatSession:
    """Manage a single interactive chat session with one agent."""

    def __init__(self, agent_key: str) -> None:
        """Initialize a chat session for the given agent."""
        self.agent_key = agent_key

        self.agent_session = create_agent_session()

        if not self.agent_session.is_valid_agent(agent_key):
            raise ValueError(f"Unknown agent: {agent_key}")

        self.engine = self.agent_session.get_agent(agent_key)

        self.last_response: str | None = None
        self.pending_output: str | None = None
        self.pending_output_overwrite: bool = False
        self.pending_reads: list[str] = []

    def add_pending_read(self, pattern: str) -> list[str]:
        """Queue one or more files to be included in the next prompt."""
        paths = resolve_read_paths(pattern)

        queued: list[str] = []

        for path in paths:
            path_str = str(path)
            read_file(path_str)

            if path_str in self.pending_reads:
                continue

            self.pending_reads.append(path_str)
            queued.append(path_str)

        return queued

    def send(self, prompt: str) -> str:
        """Send a prompt to the current agent and return the response."""
        effective_prompt = prompt

        if self.pending_reads:
            contexts: list[str] = []

            for path in self.pending_reads:
                content = read_file(path)
                contexts.append(
                    f"--- file: {path} ---\n{content}\n--- end file: {path} ---"
                )

            effective_prompt = "\n\n".join(contexts) + "\n\n" + prompt

        try:
            response = self.engine.call(effective_prompt)
        finally:
            self.pending_reads = []

        self.last_response = response

        if self.pending_output is not None:
            output_path = self.pending_output
            overwrite = self.pending_output_overwrite

            self.pending_output = None
            self.pending_output_overwrite = False

            if overwrite:
                write_file(output_path, response)
            else:
                write_new_file(output_path, response)

        return response

    def write_last_response(self, path: str, overwrite: bool = False) -> int:
        """Write the most recent assistant response to a file."""
        if self.last_response is None:
            raise ValueError(
                "no assistant response to write; send a prompt first, or use :o / :O to save the next response"
            )

        if overwrite:
            return write_file(path, self.last_response)

        return write_new_file(path, self.last_response)

    def set_pending_output(self, path: str, overwrite: bool = False) -> None:
        """Reserve a file path for writing the next assistant response."""
        if not overwrite:
            ensure_new_file(path)

        self.pending_output = path
        self.pending_output_overwrite = overwrite
