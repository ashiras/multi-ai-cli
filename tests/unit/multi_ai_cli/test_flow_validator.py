import unittest
from unittest.mock import patch

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

VALID_COMMANDS = BUILTIN_COMMANDS | AGENTS


class FlowValidatorTest(unittest.TestCase):

    def validate(self, text: str) -> None:
        ast = parse_flow(text)

        with patch(
            "multi_ai_cli.flow_validator.get_valid_commands",
            return_value=VALID_COMMANDS,
        ):
            validate_flow(ast)

    def validate_error(
        self,
        text: str,
        expected_message: str,
    ) -> None:
        ast = parse_flow(text)

        with patch(
            "multi_ai_cli.flow_validator.get_valid_commands",
            return_value=VALID_COMMANDS,
        ):
            with self.assertRaisesRegex(
                FlowValidationError,
                expected_message,
            ):
                validate_flow(ast)

    # ---------------------------------------------------------
    # Valid flows
    # ---------------------------------------------------------

    def test_simple_sequence_is_valid(self) -> None:
        self.validate(
            "@gpt -> @gemini -> @claude"
        )

    def test_same_agent_sequential_reuse_is_valid(self) -> None:
        self.validate(
            "@gpt -> @gemini -> @gpt"
        )

    def test_simple_parallel_with_distinct_agents_is_valid(
        self,
    ) -> None:
        self.validate(
            "[ @gpt || @gemini ]"
        )

    def test_sequence_branches_with_distinct_agents_are_valid(
        self,
    ) -> None:
        self.validate(
            "[ "
            "( @gpt -> @gemini ) "
            "|| "
            "( @grok -> @local ) "
            "]"
        )

    def test_agent_can_be_reused_after_parallel_join(
        self,
    ) -> None:
        self.validate(
            """
            [
              ( @gpt -> [ @gemini || @claude ] )
              ||
              ( @grok -> @local )
            ] -> @grok
            """
        )

    def test_pause_after_parallel_is_valid(self) -> None:
        self.validate(
            """
            [
              ( @gpt -> @gemini )
              ||
              @grok
            ]
            ->
            @pause
            ->
            @claude
            """
        )

    def test_same_builtin_command_in_parallel_is_valid(
        self,
    ) -> None:
        self.validate(
            '[ @sh "echo one" || @sh "echo two" ]'
        )

    # ---------------------------------------------------------
    # Unknown commands
    # ---------------------------------------------------------

    def test_unknown_command_is_rejected(self) -> None:
        self.validate_error(
            "@unknown hello",
            "Unknown command",
        )

    def test_unknown_command_inside_parallel_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            "[ @gpt || @unknown ]",
            "Unknown command",
        )

    # ---------------------------------------------------------
    # @pause
    # ---------------------------------------------------------

    def test_pause_directly_inside_parallel_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            "[ @gpt || @pause ]",
            "@pause cannot be used inside a parallel block",
        )

    def test_pause_inside_sequence_branch_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            """
            [
              ( @gpt -> @pause -> @gemini )
              ||
              @grok
            ]
            """,
            "@pause cannot be used inside a parallel block",
        )

    def test_pause_inside_nested_parallel_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            """
            [
              @gpt
              ||
              [
                @gemini
                ||
                ( @claude -> @pause )
              ]
            ]
            """,
            "@pause cannot be used inside a parallel block",
        )

    # ---------------------------------------------------------
    # Duplicate Agents
    # ---------------------------------------------------------

    def test_duplicate_agent_in_direct_parallel_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            "[ @gpt || @gpt ]",
            "duplicate Agent",
        )

    def test_duplicate_agent_across_sequence_branches_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            """
            [
              ( @gpt -> @gemini )
              ||
              ( @claude -> @gpt )
            ]
            """,
            "duplicate Agent",
        )

    def test_nested_agent_conflict_is_rejected(
        self,
    ) -> None:
        self.validate_error(
            """
            [
              ( @gpt -> [ @gemini || @claude ] )
              ||
              ( @grok -> @gemini )
            ]
            """,
            "duplicate Agent",
        )

    def test_same_agent_twice_inside_one_sequence_branch_is_valid(
        self,
    ) -> None:
        self.validate(
            """
            [
              ( @gpt -> @gemini -> @gpt )
              ||
              @grok
            ]
            """
        )


if __name__ == "__main__":
    unittest.main()