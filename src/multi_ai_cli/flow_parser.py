"""
Recursive parser for the Multi-AI Sequence DSL.

Grammar:

    Flow       ::= Sequence

    Sequence   ::= Node ("->" Node)*

    Node       ::= Command
                 | Group
                 | Parallel

    Group      ::= "(" Sequence ")"

    Parallel   ::= "[" Branch ("||" Branch)+ "]"

    Branch     ::= Command
                 | Group
                 | Parallel

Important:
    A sequence used as a parallel branch must be grouped explicitly.

    Valid:

        [ ( @gpt -> @gemini ) || @grok ]

    Invalid:

        [ @gpt -> @gemini || @grok ]

This parser handles syntax only.

Semantic validation such as:

    - unknown commands
    - duplicate agents across parallel branches
    - @pause inside parallel structures

is intentionally handled in a later validation phase.
"""

from __future__ import annotations

import shlex

from .flow_ast import (
    CommandNode,
    FlowNode,
    ParallelNode,
    SequenceNode,
)


class FlowSyntaxError(ValueError):
    """
    Raised when Sequence DSL syntax is invalid.
    """

    def __init__(self, message: str, position: int) -> None:
        """Initialize a syntax error with its source position."""
        super().__init__(f"{message} (position {position})")
        self.position = position


class FlowParser:
    """
    Recursive descent parser for the Multi-AI Sequence DSL.
    """

    def __init__(self, text: str) -> None:
        """Initialize the parser with normalized Flow text."""
        self.text = self._normalize_input(text)
        self.pos = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self) -> SequenceNode:
        """
        Parse the full Flow definition.
        """
        self._skip_whitespace()

        if self._eof():
            raise FlowSyntaxError(
                "Flow definition is empty.",
                self.pos,
            )

        node = self._parse_sequence()

        self._skip_whitespace()

        if not self._eof():
            raise FlowSyntaxError(
                f"Unexpected token near {self.text[self.pos : self.pos + 20]!r}.",
                self.pos,
            )

        return node

    # ------------------------------------------------------------------
    # Grammar
    # ------------------------------------------------------------------

    def _parse_sequence(self) -> SequenceNode:
        """
        Parse ``Sequence ::= Node ("->" Node)*``.
        """
        children: list[FlowNode] = [self._parse_node()]

        while True:
            self._skip_whitespace()

            if not self._starts_with("->"):
                break

            self.pos += 2
            self._skip_whitespace()

            if (
                self._eof()
                or self._starts_with("||")
                or self._current_is("]")
                or self._current_is(")")
            ):
                raise FlowSyntaxError(
                    "Expected a node after '->'.",
                    self.pos,
                )

            children.append(self._parse_node())

        return SequenceNode(children=children)

    def _parse_node(self) -> FlowNode:
        """
        Parse ``Node ::= Command | Group | Parallel``.
        """
        self._skip_whitespace()

        if self._eof():
            raise FlowSyntaxError(
                "Expected a node.",
                self.pos,
            )

        if self._current_is("("):
            return self._parse_group()

        if self._current_is("["):
            return self._parse_parallel()

        if self._current_is("]"):
            raise FlowSyntaxError(
                "Unexpected ']'.",
                self.pos,
            )

        if self._current_is(")"):
            raise FlowSyntaxError(
                "Unexpected ')'.",
                self.pos,
            )

        if self._starts_with("||"):
            raise FlowSyntaxError(
                "Unexpected '||'.",
                self.pos,
            )

        if self._starts_with("->"):
            raise FlowSyntaxError(
                "Unexpected '->'.",
                self.pos,
            )

        return self._parse_command()

    def _parse_group(self) -> SequenceNode:
        """
        Parse ``Group ::= "(" Sequence ")"``.
        """
        self._consume("(")
        self._skip_whitespace()

        if self._current_is(")"):
            raise FlowSyntaxError(
                "Empty sequence group '()' is not allowed.",
                self.pos,
            )

        sequence = self._parse_sequence()

        self._skip_whitespace()

        if not self._current_is(")"):
            raise FlowSyntaxError(
                "Expected ')' to close sequence group.",
                self.pos,
            )

        self._consume(")")

        return sequence

    def _parse_parallel(self) -> ParallelNode:
        """
        Parse ``Parallel ::= "[" Branch ("||" Branch)+ "]"``.

        A bare sequence is intentionally not accepted as a branch.

        Use:

            [ ( A -> B ) || C ]

        instead of:

            [ A -> B || C ]
        """
        self._consume("[")
        self._skip_whitespace()

        if self._current_is("]"):
            raise FlowSyntaxError(
                "Empty parallel block '[]' is not allowed.",
                self.pos,
            )

        branches: list[FlowNode] = []

        while True:
            branch = self._parse_node()
            branches.append(branch)

            self._skip_whitespace()

            # Sequence inside a parallel branch must be explicit.
            if self._starts_with("->"):
                raise FlowSyntaxError(
                    "Sequence branches inside '[...]' must be grouped with '(...)'.",
                    self.pos,
                )

            if self._starts_with("||"):
                self.pos += 2
                self._skip_whitespace()

                if self._eof() or self._current_is("]") or self._starts_with("||"):
                    raise FlowSyntaxError(
                        "Expected a branch after '||'.",
                        self.pos,
                    )

                continue

            if self._current_is("]"):
                self._consume("]")
                break

            raise FlowSyntaxError(
                "Expected '||' or ']' in parallel block.",
                self.pos,
            )

        if len(branches) < 2:
            raise FlowSyntaxError(
                "Parallel block requires at least two branches.",
                self.pos,
            )

        return ParallelNode(branches=branches)

    def _parse_command(self) -> CommandNode:
        """
        Parse one command until a structural DSL token is reached.

        Structural tokens are recognized only outside quoted strings.
        """
        start = self.pos
        quote: str | None = None

        while not self._eof():
            ch = self._current()

            # Preserve escaped characters.
            if ch == "\\" and self.pos + 1 < len(self.text):
                self.pos += 2
                continue

            if ch in ('"', "'"):
                if quote is None:
                    quote = ch
                elif quote == ch:
                    quote = None

                self.pos += 1
                continue

            if quote is None:
                if self._starts_with("->"):
                    break

                if self._starts_with("||"):
                    break

                if ch in "[]()":
                    break

            self.pos += 1

        if quote is not None:
            raise FlowSyntaxError(
                "Unterminated quoted string.",
                start,
            )

        raw_command = self.text[start : self.pos].strip()

        if not raw_command:
            raise FlowSyntaxError(
                "Expected a command.",
                start,
            )

        try:
            tokens = shlex.split(raw_command)
        except ValueError as exc:
            raise FlowSyntaxError(
                f"Command parse error: {exc}",
                start,
            ) from exc

        if not tokens:
            raise FlowSyntaxError(
                "Expected a command.",
                start,
            )

        # Preserve compatibility with the existing sequence parser,
        # which accepts command names with or without '@'.
        if not tokens[0].startswith("@"):
            tokens[0] = "@" + tokens[0]

        return CommandNode(tokens=tokens)

    # ------------------------------------------------------------------
    # Input normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_input(text: str) -> str:
        """
        Remove blank lines and full-line comments.

        This intentionally follows the existing sequence parser behavior:
        non-empty lines are joined with spaces.
        """
        lines: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("#"):
                continue

            lines.append(stripped)

        return " ".join(lines)

    # ------------------------------------------------------------------
    # Scanner helpers
    # ------------------------------------------------------------------

    def _skip_whitespace(self) -> None:
        while not self._eof() and self._current().isspace():
            self.pos += 1

    def _consume(self, token: str) -> None:
        if not self._starts_with(token):
            raise FlowSyntaxError(
                f"Expected {token!r}.",
                self.pos,
            )

        self.pos += len(token)

    def _starts_with(self, token: str) -> bool:
        return self.text.startswith(
            token,
            self.pos,
        )

    def _current(self) -> str:
        if self._eof():
            return ""

        return self.text[self.pos]

    def _current_is(self, token: str) -> bool:
        if self._eof():
            return False

        return self.text[self.pos] == token

    def _eof(self) -> bool:
        return self.pos >= len(self.text)


def parse_flow(text: str) -> SequenceNode:
    """
    Parse a Multi-AI Flow definition into an AST.

    Args:
        text: Raw Sequence DSL text.

    Returns:
        SequenceNode: Root AST node.

    Raises:
        FlowSyntaxError: If the syntax is invalid.
    """
    return FlowParser(text).parse()
