import unittest
from unittest.mock import patch

from multi_ai_cli.parsers import parse_sequence_steps


VALID_COMMANDS = {
    "gpt",
    "gemini",
    "claude",
    "grok",
    "local",
}


class LegacySequenceParserTest(unittest.TestCase):

    @patch(
        "multi_ai_cli.parsers.get_valid_commands",
        return_value=VALID_COMMANDS,
    )
    def test_sequential_flow(self, _mock_valid_commands) -> None:
        result = parse_sequence_steps(
            "@gpt hello! -> @gemini hello! -> @claude hello!"
        )

        self.assertEqual(
            result,
            [
                [["@gpt", "hello!"]],
                [["@gemini", "hello!"]],
                [["@claude", "hello!"]],
            ],
        )

    @patch(
        "multi_ai_cli.parsers.get_valid_commands",
        return_value=VALID_COMMANDS,
    )
    def test_sequence_then_parallel(self, _mock_valid_commands) -> None:
        result = parse_sequence_steps(
            "@gpt hello! -> "
            "[ @gemini hello! || @claude hello! ]"
        )

        self.assertEqual(
            result,
            [
                [["@gpt", "hello!"]],
                [
                    ["@gemini", "hello!"],
                    ["@claude", "hello!"],
                ],
            ],
        )

    @patch(
        "multi_ai_cli.parsers.get_valid_commands",
        return_value=VALID_COMMANDS,
    )
    def test_parallel_then_sequence(self, _mock_valid_commands) -> None:
        result = parse_sequence_steps(
            "[ @gemini hello! || @claude hello! ] "
            "-> @gpt hello!"
        )

        self.assertEqual(
            result,
            [
                [
                    ["@gemini", "hello!"],
                    ["@claude", "hello!"],
                ],
                [["@gpt", "hello!"]],
            ],
        )

    @patch(
        "multi_ai_cli.parsers.get_valid_commands",
        return_value=VALID_COMMANDS,
    )
    def test_simple_parallel(self, _mock_valid_commands) -> None:
        result = parse_sequence_steps(
            "[ @gpt hello! || @grok hello! ]"
        )

        self.assertEqual(
            result,
            [
                [
                    ["@gpt", "hello!"],
                    ["@grok", "hello!"],
                ],
            ],
        )


if __name__ == "__main__":
    unittest.main()