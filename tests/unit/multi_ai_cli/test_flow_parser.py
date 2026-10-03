import unittest

from multi_ai_cli.flow_ast import (
    CommandNode,
    ParallelNode,
    SequenceNode,
)
from multi_ai_cli.flow_parser import (
    FlowSyntaxError,
    parse_flow,
)


class FlowParserTest(unittest.TestCase):

    def test_single_command(self) -> None:
        ast = parse_flow(
            "@gpt hello!"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    CommandNode(
                        tokens=["@gpt", "hello!"]
                    ),
                ]
            ),
        )

    def test_simple_sequence(self) -> None:
        ast = parse_flow(
            "@gpt hello! -> @gemini hello!"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    CommandNode(
                        tokens=["@gpt", "hello!"]
                    ),
                    CommandNode(
                        tokens=["@gemini", "hello!"]
                    ),
                ]
            ),
        )

    def test_simple_parallel(self) -> None:
        ast = parse_flow(
            "[ @gpt hello! || @gemini hello! ]"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    ParallelNode(
                        branches=[
                            CommandNode(
                                tokens=["@gpt", "hello!"]
                            ),
                            CommandNode(
                                tokens=["@gemini", "hello!"]
                            ),
                        ]
                    ),
                ]
            ),
        )

    def test_sequence_then_parallel(self) -> None:
        ast = parse_flow(
            "@gpt hello! -> "
            "[ @gemini hello! || @claude hello! ]"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    CommandNode(
                        tokens=["@gpt", "hello!"]
                    ),
                    ParallelNode(
                        branches=[
                            CommandNode(
                                tokens=["@gemini", "hello!"]
                            ),
                            CommandNode(
                                tokens=["@claude", "hello!"]
                            ),
                        ]
                    ),
                ]
            ),
        )

    def test_parallel_then_sequence(self) -> None:
        ast = parse_flow(
            "[ @gemini hello! || @claude hello! ] "
            "-> @gpt hello!"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    ParallelNode(
                        branches=[
                            CommandNode(
                                tokens=["@gemini", "hello!"]
                            ),
                            CommandNode(
                                tokens=["@claude", "hello!"]
                            ),
                        ]
                    ),
                    CommandNode(
                        tokens=["@gpt", "hello!"]
                    ),
                ]
            ),
        )

    def test_grouped_sequence_branch(self) -> None:
        ast = parse_flow(
            "[ "
            "( @gpt hello! -> @gemini hello! ) "
            "|| "
            "@grok hello! "
            "] -> @claude hello!"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    ParallelNode(
                        branches=[
                            SequenceNode(
                                children=[
                                    CommandNode(
                                        tokens=[
                                            "@gpt",
                                            "hello!",
                                        ]
                                    ),
                                    CommandNode(
                                        tokens=[
                                            "@gemini",
                                            "hello!",
                                        ]
                                    ),
                                ]
                            ),
                            CommandNode(
                                tokens=[
                                    "@grok",
                                    "hello!",
                                ]
                            ),
                        ]
                    ),
                    CommandNode(
                        tokens=[
                            "@claude",
                            "hello!",
                        ]
                    ),
                ]
            ),
        )

    def test_nested_parallel(self) -> None:
        ast = parse_flow(
            "[ "
            "@gemini hello! "
            "|| "
            "[ @claude hello! || @gpt hello! ] "
            "]"
        )

        self.assertEqual(
            ast,
            SequenceNode(
                children=[
                    ParallelNode(
                        branches=[
                            CommandNode(
                                tokens=[
                                    "@gemini",
                                    "hello!",
                                ]
                            ),
                            ParallelNode(
                                branches=[
                                    CommandNode(
                                        tokens=[
                                            "@claude",
                                            "hello!",
                                        ]
                                    ),
                                    CommandNode(
                                        tokens=[
                                            "@gpt",
                                            "hello!",
                                        ]
                                    ),
                                ]
                            ),
                        ]
                    ),
                ]
            ),
        )

    def test_complex_nested_flow(self) -> None:
        ast = parse_flow(
            """
            [
              ( @gpt -> [ @gemini || @claude ] )
              ||
              ( @grok -> @local )
            ] -> @grok
            """
        )

        self.assertIsInstance(
            ast,
            SequenceNode,
        )

        self.assertEqual(
            len(ast.children),
            2,
        )

        self.assertIsInstance(
            ast.children[0],
            ParallelNode,
        )

        self.assertEqual(
            ast.children[1],
            CommandNode(
                tokens=["@grok"]
            ),
        )

    def test_ungrouped_sequence_branch_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            FlowSyntaxError,
            "must be grouped",
        ):
            parse_flow(
                "[ @gpt -> @gemini || @grok ]"
            )

    def test_empty_parallel_is_rejected(self) -> None:
        with self.assertRaises(
            FlowSyntaxError
        ):
            parse_flow("[]")

    def test_empty_group_is_rejected(self) -> None:
        with self.assertRaises(
            FlowSyntaxError
        ):
            parse_flow("()")

    def test_missing_parallel_branch_is_rejected(self) -> None:
        with self.assertRaises(
            FlowSyntaxError
        ):
            parse_flow(
                "[ @gpt || ]"
            )

    def test_missing_sequence_node_is_rejected(self) -> None:
        with self.assertRaises(
            FlowSyntaxError
        ):
            parse_flow(
                "( @gpt -> )"
            )


if __name__ == "__main__":
    unittest.main()