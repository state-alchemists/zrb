from zrb.util.string.name import PREFIXES, SUFFIXES, get_random_name


def test_get_random_name_default():
    name = get_random_name()
    parts = name.split("-")
    assert len(parts) == 3
    assert parts[0] in PREFIXES
    assert parts[1] in SUFFIXES
    assert len(parts[2]) == 4
    assert parts[2].isdigit()


def test_get_random_name_no_digit():
    name = get_random_name(add_random_digit=False)
    parts = name.split("-")
    assert len(parts) == 2
    assert parts[0] in PREFIXES
    assert parts[1] in SUFFIXES


def test_get_random_name_custom_separator():
    name = get_random_name(separator="_")
    parts = name.split("_")
    assert len(parts) == 3
    assert parts[0] in PREFIXES
    assert parts[1] in SUFFIXES
    assert len(parts[2]) == 4


def test_get_random_name_custom_digit_count():
    name = get_random_name(digit_count=6)
    parts = name.split("-")
    assert len(parts) == 3
    assert len(parts[2]) == 6
