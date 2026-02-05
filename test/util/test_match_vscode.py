from zrb.util.match import fuzzy_match


def test_match_vscode_preference():
    query = "abc/def.py"
    target_good = "abc/whatever/def.py"
    target_bad = "ararabbbbbcc/def.py"

    matched_good, score_good = fuzzy_match(target_good, query)
    matched_bad, score_bad = fuzzy_match(target_bad, query)

    assert matched_good
    assert matched_bad

    print(f"Good score: {score_good}")
    print(f"Bad score: {score_bad}")

    assert score_good < score_bad


def test_match_boundary_preference():
    query = "zrb config"
    target_short = "zrb/config.py"
    target_long = "zrb_long_prefix_config.py"

    _, score_short = fuzzy_match(target_short, query)
    _, score_long = fuzzy_match(target_long, query)

    assert score_short < score_long


def test_contiguous_wins():
    query = "abc"
    target_contiguous = "abc"
    target_subsequence = "a_b_c"

    _, score_cont = fuzzy_match(target_contiguous, query)
    _, score_sub = fuzzy_match(target_subsequence, query)

    assert score_cont < score_sub
