import unittest

from multi_ai_cli.flow_ast import (
    CommandNode,
    ParallelNode,
    SequenceNode,
)


class FlowAstTest(unittest.TestCase):
    def test_ast_construction(self) -> None:
        cmd1 = CommandNode(tokens=["@gpt", "hello!"])
        cmd2 = CommandNode(tokens=["@gemini", "hi!"])
        seq = SequenceNode(children=[cmd1, cmd2])
        parallel = ParallelNode(branches=[seq, cmd2])

        self.assertEqual(len(parallel.branches), 2)
        self.assertIsInstance(parallel.branches[0], SequenceNode)
        self.assertIsInstance(parallel.branches[1], CommandNode)
