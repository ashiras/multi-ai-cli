from multi_ai_cli.agent_factory import AgentFactory
from multi_ai_cli.registry import agent_registry
from multi_ai_cli.session import AgentSession
import multi_ai_cli.config as multi_ai_config

from portable_agent_chat.files import read_file, write_new_file, ensure_new_file


def create_agent_session() -> AgentSession:
    factory = AgentFactory()

    return AgentSession(
        registry=agent_registry,
        factory=factory,
        legacy_sdk_map=multi_ai_config.legacy_sdk_map,
    )


class ChatSession:
    def __init__(self, agent_key: str):
        self.agent_key = agent_key

        self.agent_session = create_agent_session()

        if not self.agent_session.is_valid_agent(agent_key):
            raise ValueError(f"Unknown agent: {agent_key}")

        self.engine = self.agent_session.get_agent(agent_key)

        self.last_response: str | None = None
        self.pending_output: str | None = None
        self.pending_reads: list[str] = []

    def add_pending_read(self, path: str) -> None:
        # :r 実行時点で存在・読み込み可能性を確認する
        read_file(path)
        self.pending_reads.append(path)

    def send(self, prompt: str) -> str:
        effective_prompt = prompt

        if self.pending_reads:
            contexts: list[str] = []

            for path in self.pending_reads:
                content = read_file(path)

                contexts.append(
                    f"--- file: {path} ---\n"
                    f"{content}\n"
                    f"--- end file: {path} ---"
                )

            effective_prompt = (
                "\n\n".join(contexts)
                + "\n\n"
                + prompt
            )

        try:
            response = self.engine.call(effective_prompt)
        finally:
            self.pending_reads = []

        self.last_response = response

        if self.pending_output is not None:
            write_new_file(self.pending_output, response)
            self.pending_output = None

        return response

    def write_last_response(self, path: str) -> int:
        if self.last_response is None:
            raise ValueError("no assistant response to write")

        return write_new_file(path, self.last_response)
    
    def set_pending_output(self, path: str) -> None:
        ensure_new_file(path)
        self.pending_output = path