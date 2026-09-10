from zrb.util.cli.ansi import strip_ansi


def test_strip_ansi_removes_color_codes():
    assert strip_ansi("\033[1;34mhello\033[0m") == "hello"


def test_strip_ansi_leaves_plain_text_untouched():
    assert strip_ansi("plain text") == "plain text"


def test_strip_ansi_removes_multiple_sequences():
    styled = "\033[2m🧰 call | Tool {'a': 1}\033[0m\n\033[2m🔠 Executed\033[0m\n"
    assert strip_ansi(styled) == "🧰 call | Tool {'a': 1}\n🔠 Executed\n"
