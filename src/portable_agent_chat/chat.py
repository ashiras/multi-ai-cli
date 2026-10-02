"""Chat session management for prompt execution and file integration."""

import multi_ai_cli.config as multi_ai_config
from multi_ai_cli.agent_factory import AgentFactory
from multi_ai_cli.registry import agent_registry
from multi_ai_cli.session import AgentSession
from portable_agent_chat.files import (
    ensure_new_file,
    read_file,
    resolve_read_paths,
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
        """Initialize a chat session for the given agent.

        Args:
            agent_key: Registered agent name to use.

        Raises:
            ValueError: If the agent name is unknown.
        """
        self.agent_key = agent_key

        self.agent_session = create_agent_session()

        if not self.agent_session.is_valid_agent(agent_key):
            raise ValueError(f"Unknown agent: {agent_key}")

        self.engine = self.agent_session.get_agent(agent_key)

        self.last_response: str | None = None
        self.pending_output: str | None = None
        self.pending_reads: list[str] = []

    def add_pending_read(self, pattern: str) -> list[str]:
        """Queue one or more files to be included in the next prompt.

        The path may contain glob patterns such as ``*.py`` or ``**/*.py``.
        Matching files are validated immediately when the command is issued.

        Args:
            pattern: File path or glob pattern to include in the next request.

        Returns:
            The list of matched file paths.

        Raises:
            FileNotFoundError: If no files match the path or pattern.
            OSError: If a matched file cannot be read.
        """
        paths = resolve_read_paths(pattern)

        queued: list[str] = []

        for path in paths:
            path_str = str(path)

            # Validate readability now rather than waiting until send().
            read_file(path_str)

            self.pending_reads.append(path_str)
            queued.append(path_str)

        return queued

    def send(self, prompt: str) -> str:
        """Send a prompt to the current agent and return the response.

        Any queued file reads are embedded into the effective prompt before
        sending. Queued reads are always cleared after the request attempt.

        Args:
            prompt: User prompt text.

        Returns:
            The assistant response text.
        """
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
            # Clear queued reads even if the model call fails.
            self.pending_reads = []

        self.last_response = response

        if self.pending_output is not None:
            write_new_file(self.pending_output, response)
            self.pending_output = None

        return response

    def write_last_response(self, path: str) -> int:
        """Write the most recent assistant response to a new file.

        Args:
            path: Destination file path.

        Returns:
            The number of bytes written.

        Raises:
            ValueError: If no assistant response is available yet.
            FileExistsError: If the destination file already exists.
        """
        if self.last_response is None:
            raise ValueError("no assistant response to write")

        return write_new_file(path, self.last_response)

    def set_pending_output(self, path: str) -> None:
        """Reserve a file path for writing the next assistant response.

        Args:
            path: Destination file path for the next response.

        Raises:
            FileExistsError: If the destination path already exists.
        """
        ensure_new_file(path)
        self.pending_output = path
