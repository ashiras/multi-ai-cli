import unittest

from multi_ai_cli.flow_parser import (
    FlowSyntaxError,
    parse_flow,
)


class FlowAstSyntaxTest(unittest.TestCase):
    def test_missing_closing_bracket(self) -> None:
        with self.assertRaises(FlowSyntaxError):
            parse_flow("[ @gpt hello! || @gemini hello!")

    def test_invalid_arrow_syntax(self) -> None:
        with self.assertRaises(FlowSyntaxError):
            parse_flow("@gpt hello! -> -> @gemini hello!")

    def test_empty_branch(self) -> None:
        with self.assertRaises(FlowSyntaxError):
            parse_flow("[ @gpt hello! || || @gemini hello! ]")
