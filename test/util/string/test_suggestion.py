from zrb.util.string.suggestion import format_suggestion, suggest_name


def test_suggest_name_finds_a_near_miss():
    assert suggest_name("nmae", ["name", "age"]) == ["name"]


def test_suggest_name_is_empty_when_nothing_is_close():
    assert suggest_name("xyzzyqqq", ["name", "age"]) == []


def test_suggest_name_handles_empty_inputs():
    assert suggest_name("", ["name"]) == []
    assert suggest_name("name", []) == []


def test_suggest_name_respects_the_limit():
    candidates = ["encode", "encoded", "encoder", "encodes"]

    assert len(suggest_name("encod", candidates, limit=2)) == 2


def test_suggest_name_orders_best_match_first():
    assert suggest_name("encode", ["encoder", "encode"])[0] == "encode"


def test_format_suggestion_single_match():
    assert format_suggestion("nmae", ["name"]) == " Did you mean 'name'?"


def test_format_suggestion_multiple_matches():
    result = format_suggestion("encoode", ["encode", "decode"])

    assert result == " Did you mean one of 'encode', 'decode'?"


def test_format_suggestion_is_empty_when_nothing_is_close():
    assert format_suggestion("xyzzyqqq", ["name"]) == ""


def test_format_suggestion_starts_with_a_space_so_it_can_be_appended():
    """Callers concatenate this onto a message unconditionally."""
    result = format_suggestion("nmae", ["name"])

    assert result.startswith(" ")
