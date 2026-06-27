from zrb.util.truncate import truncate_chars, truncate_items, truncate_text


# --- truncate_text ---
def test_truncate_text_no_truncation():
    text = "a\nb\nc"
    out, truncated = truncate_text(text, 100)
    assert out == text
    assert truncated is False


def test_truncate_text_keep_head():
    text = "\n".join(f"line{i}" for i in range(100))
    out, truncated = truncate_text(text, 30, keep="head")
    assert truncated is True
    assert out.startswith("line0")
    assert out.endswith("...[TRUNCATED]")
    assert "line99" not in out


def test_truncate_text_keep_tail():
    text = "\n".join(f"line{i}" for i in range(100))
    out, truncated = truncate_text(text, 30, keep="tail")
    assert truncated is True
    assert out.startswith("[TRUNCATED]...")
    assert "line99" in out
    assert "line0\n" not in out


def test_truncate_text_keep_tail_zero_max_chars():
    out, truncated = truncate_text("a\nb\nc", 0, keep="tail")
    assert truncated is True
    assert out == "[TRUNCATED]...\n"


def test_truncate_text_keep_tail_negative_max_chars():
    out, truncated = truncate_text("a\nb\nc", -2, keep="tail")
    assert truncated is True
    assert out == "[TRUNCATED]...\n"


def test_truncate_text_snaps_to_line_boundary_head():
    text = "aaaa\nbbbb\ncccc\n"
    out, _ = truncate_text(text, 6, keep="head")
    assert out == "aaaa\n...[TRUNCATED]"


def test_truncate_text_keep_head_single_long_line():
    text = "x" * 50
    out, truncated = truncate_text(text, 10, keep="head")
    assert truncated is True
    assert out == "x" * 10 + "\n...[TRUNCATED]"


# --- truncate_items ---
def test_truncate_items_no_truncation():
    items = ["a", "b", "c"]
    kept, omitted = truncate_items(items, 1000)
    assert kept == items
    assert omitted == 0


def test_truncate_items_truncates():
    items = [f"file{i}.py" for i in range(100)]
    kept, omitted = truncate_items(items, 30)
    assert omitted > 0
    assert len(kept) + omitted == 100
    assert kept[0] == "file0.py"


def test_truncate_items_keeps_first_even_if_huge():
    items = ["x" * 1000, "y", "z"]
    kept, omitted = truncate_items(items, 10)
    assert kept == ["x" * 1000]
    assert omitted == 2


# --- truncate_chars (unchanged) ---
def test_truncate_chars_no_truncation():
    assert truncate_chars("short", 100) == "short"


def test_truncate_chars_truncates():
    out = truncate_chars("abcdef", 3)
    assert out.startswith("abc")
    assert "TRUNCATED" in out
