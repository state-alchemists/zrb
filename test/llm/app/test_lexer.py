import pytest
from prompt_toolkit.document import Document

from zrb.llm.app.lexer import CLIStyleLexer


def test_cli_style_lexer_initialization():
    """Test that CLIStyleLexer can be instantiated."""
    lexer = CLIStyleLexer()
    assert lexer is not None
    assert isinstance(lexer, CLIStyleLexer)


def test_lex_document_returns_callable():
    """Test that lex_document returns a callable function."""
    lexer = CLIStyleLexer()
    document = Document(text="Hello world")
    get_line = lexer.lex_document(document)

    assert callable(get_line)
    assert get_line(0) == [("", "Hello world")]


def test_lex_document_with_ansi_reset():
    """Test lexing with ANSI reset sequence."""
    lexer = CLIStyleLexer()
    # \x1B[0m is ANSI reset
    document = Document(text="\x1b[31mRed\x1b[0m Normal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 2
    # First token: red text
    assert tokens[0] == ("#ff0000", "Red")
    # Second token: normal text after reset (reset doesn't create a token)
    assert tokens[1] == ("", " Normal")


def test_lex_document_with_bold_ansi():
    """Test lexing with bold ANSI sequence."""
    lexer = CLIStyleLexer()
    # \x1B[1m is bold
    document = Document(text="\x1b[1mBold text")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert tokens[0] == ("bold", "Bold text")


def test_lex_document_with_multiple_attributes():
    """Test lexing with multiple ANSI attributes."""
    lexer = CLIStyleLexer()
    # \x1B[1;31m is bold red
    document = Document(text="\x1b[1;31mBold Red")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    # Should have both bold and red
    assert "bold" in tokens[0][0]
    assert "#ff0000" in tokens[0][0]
    assert tokens[0][1] == "Bold Red"


def test_lex_document_with_background_color():
    """Test lexing with background color."""
    lexer = CLIStyleLexer()
    # \x1B[41m is red background
    document = Document(text="\x1b[41mRed BG")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert "bg:#ff0000" in tokens[0][0]
    assert tokens[0][1] == "Red BG"


def test_lex_document_with_bright_colors():
    """Test lexing with bright colors (90-97 range)."""
    lexer = CLIStyleLexer()
    # \x1B[91m is bright red
    document = Document(text="\x1b[91mBright Red")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert tokens[0] == ("#ff5555", "Bright Red")


def test_lex_document_with_literal_033_escape():
    """Test lexing with literal \033 escape sequence (not \x1b)."""
    lexer = CLIStyleLexer()
    # \033[31m is also red (literal escape)
    document = Document(text="\033[31mRed with literal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert tokens[0] == ("#ff0000", "Red with literal")


def test_lex_document_multiline():
    """Test lexing with multiple lines and state persistence."""
    lexer = CLIStyleLexer()
    # Red should persist to second line
    document = Document(text="\x1b[31mLine 1\nLine 2")
    get_line = lexer.lex_document(document)

    # First line should be red
    tokens_line0 = get_line(0)
    assert len(tokens_line0) == 1
    assert tokens_line0[0] == ("#ff0000", "Line 1")

    # Second line should also be red (state persists)
    tokens_line1 = get_line(1)
    assert len(tokens_line1) == 1
    assert tokens_line1[0] == ("#ff0000", "Line 2")


def test_lex_document_reset_between_lines():
    """Test that reset works between lines."""
    lexer = CLIStyleLexer()
    # Red on first line, reset, normal on second
    document = Document(text="\x1b[31mLine 1\x1b[0m\nLine 2")
    get_line = lexer.lex_document(document)

    # First line: red text (reset doesn't create a token)
    tokens_line0 = get_line(0)
    assert len(tokens_line0) == 1
    assert tokens_line0[0] == ("#ff0000", "Line 1")

    # Second line: normal (reset persisted)
    tokens_line1 = get_line(1)
    assert len(tokens_line1) == 1
    assert tokens_line1[0] == ("", "Line 2")


def test_lex_document_empty_line():
    """Test lexing with empty lines."""
    lexer = CLIStyleLexer()
    document = Document(text="")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert tokens == []


def test_lex_document_line_out_of_range():
    """Test that out of range line numbers return empty list."""
    lexer = CLIStyleLexer()
    document = Document(text="Single line")
    get_line = lexer.lex_document(document)

    # Line 0 exists
    assert get_line(0) == [("", "Single line")]
    # Line 1 doesn't exist
    assert get_line(1) == []
    # Line -1 doesn't exist
    assert get_line(-1) == []


def test_lex_document_complex_sequence():
    """Test a complex ANSI sequence with multiple colors and attributes."""
    lexer = CLIStyleLexer()
    # Bold red, then normal green
    document = Document(text="\x1b[1;31mBold Red\x1b[0;32m Green")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 2
    # First: bold red
    assert "bold" in tokens[0][0]
    assert "#ff0000" in tokens[0][0]
    assert tokens[0][1] == "Bold Red"
    # Second: green (reset+green doesn't create separate token)
    assert tokens[1] == ("#00ff00", " Green")
