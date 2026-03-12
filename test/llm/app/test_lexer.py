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


# Additional tests for uncovered lines

def test_lex_document_with_italic():
    """Test lexing with italic ANSI sequence."""
    lexer = CLIStyleLexer()
    # \x1B[3m is italic
    document = Document(text="\x1b[3mItalic text")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert "italic" in tokens[0][0]


def test_lex_document_with_underline():
    """Test lexing with underline ANSI sequence."""
    lexer = CLIStyleLexer()
    # \x1B[4m is underline
    document = Document(text="\x1b[4mUnderline text")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert "underline" in tokens[0][0]


def test_lex_document_with_faint():
    """Test lexing with faint ANSI sequence."""
    lexer = CLIStyleLexer()
    # \x1B[2m is faint
    document = Document(text="\x1b[2mFaint text")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert "class:faint" in tokens[0][0]


def test_lex_document_with_reset_bold():
    """Test resetting bold/faint with code 22."""
    lexer = CLIStyleLexer()
    # Bold then reset
    document = Document(text="\x1b[1mBold\x1b[22m Normal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "bold" in tokens[0][0]
    assert tokens[0][1] == "Bold"
    # After reset
    assert tokens[1][0] == ""


def test_lex_document_with_reset_italic():
    """Test resetting italic with code 23."""
    lexer = CLIStyleLexer()
    # Italic then reset
    document = Document(text="\x1b[3mItalic\x1b[23m Normal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "italic" in tokens[0][0]


def test_lex_document_with_reset_underline():
    """Test resetting underline with code 24."""
    lexer = CLIStyleLexer()
    # Underline then reset
    document = Document(text="\x1b[4mUnder\x1b[24m Normal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "underline" in tokens[0][0]


def test_lex_document_with_all_standard_colors():
    """Test lexing with all 8 standard foreground colors (30-37)."""
    lexer = CLIStyleLexer()
    colors = [(30, "#000000"), (31, "#ff0000"), (32, "#00ff00"), (33, "#ffff00"),
              (34, "#0000ff"), (35, "#ff00ff"), (36, "#00ffff"), (37, "#ffffff")]

    for code, expected_color in colors:
        document = Document(text=f"\x1b[{code}mText")
        get_line = lexer.lex_document(document)
        tokens = get_line(0)
        assert expected_color in tokens[0][0], f"Color {code} should be {expected_color}"


def test_lex_document_with_all_standard_bg_colors():
    """Test lexing with all 8 standard background colors (40-47)."""
    lexer = CLIStyleLexer()
    colors = [(40, "#000000"), (41, "#ff0000"), (42, "#00ff00"), (43, "#ffff00"),
              (44, "#0000ff"), (45, "#ff00ff"), (46, "#00ffff"), (47, "#ffffff")]

    for code, expected_color in colors:
        document = Document(text=f"\x1b[{code}mText")
        get_line = lexer.lex_document(document)
        tokens = get_line(0)
        assert f"bg:{expected_color}" in tokens[0][0], f"BG color {code} should contain bg:{expected_color}"


def test_lex_document_with_reset_fg():
    """Test resetting foreground color with code 39."""
    lexer = CLIStyleLexer()
    document = Document(text="\x1b[31mRed\x1b[39m Normal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "#ff0000" in tokens[0][0]
    assert tokens[0][1] == "Red"
    # After reset, no color
    assert tokens[1][0] == ""


def test_lex_document_with_reset_bg():
    """Test resetting background color with code 49."""
    lexer = CLIStyleLexer()
    document = Document(text="\x1b[41mBG\x1b[49m Normal")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "bg:#ff0000" in tokens[0][0]


def test_lex_document_with_all_bright_colors():
    """Test lexing with all bright colors (90-97)."""
    lexer = CLIStyleLexer()
    colors = [(90, "#555555"), (91, "#ff5555"), (92, "#55ff55"), (93, "#ffff55"),
              (94, "#5555ff"), (95, "#ff55ff"), (96, "#55ffff"), (97, "#ffffff")]

    for code, expected_color in colors:
        document = Document(text=f"\x1b[{code}mText")
        get_line = lexer.lex_document(document)
        tokens = get_line(0)
        assert expected_color in tokens[0][0], f"Bright color {code} should be {expected_color}"


def test_lex_document_with_rgb_foreground():
    """Test lexing with RGB foreground color (38;2;r;g;b)."""
    lexer = CLIStyleLexer()
    # \x1B[38;2;255;128;64m is RGB color
    document = Document(text="\x1b[38;2;255;128;64mText")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "#ff8040" in tokens[0][0]


def test_lex_document_with_rgb_background():
    """Test lexing with RGB background color (48;2;r;g;b)."""
    lexer = CLIStyleLexer()
    # \x1B[48;2;255;128;64m is RGB background
    document = Document(text="\x1b[48;2;255;128;64mText")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "bg:#ff8040" in tokens[0][0]


def test_lex_document_with_256_color():
    """Test lexing with 256 color mode (38;5;n)."""
    lexer = CLIStyleLexer()
    # \x1B[38;5;1m is 256 color mode
    document = Document(text="\x1b[38;5;1mText")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    # Should handle 256 color mode (it skips the color index)
    assert tokens[0][1] == "Text"


def test_lex_document_with_256_bg_color():
    """Test lexing with 256 background color mode (48;5;n)."""
    lexer = CLIStyleLexer()
    document = Document(text="\x1b[48;5;1mText")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert tokens[0][1] == "Text"


def test_lex_document_empty_codes():
    """Test lexing with empty ANSI codes."""
    lexer = CLIStyleLexer()
    # \x1B[m is treated as reset
    document = Document(text="\x1b[mText")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    # Empty codes are treated as reset
    assert tokens[0][0] == ""
    assert tokens[0][1] == "Text"


def test_lex_document_multiple_codes_in_one_sequence():
    """Test multiple codes in a single ANSI sequence."""
    lexer = CLIStyleLexer()
    # Bold, faint, italic all together
    document = Document(text="\x1b[1;2;3mStyled")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert "bold" in tokens[0][0]
    assert "class:faint" in tokens[0][0]
    assert "italic" in tokens[0][0]


def test_lex_document_text_without_escape():
    """Test lexing plain text without any escape sequences."""
    lexer = CLIStyleLexer()
    document = Document(text="Just plain text here")
    get_line = lexer.lex_document(document)

    tokens = get_line(0)
    assert len(tokens) == 1
    assert tokens[0] == ("", "Just plain text here")
