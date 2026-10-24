import random

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage

from zrb.config.config import CFG
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.llm.summarizer.history_splitter import (
    FALLBACK_BUDGET_RATIO,
    TAIL_BUDGET_RATIO,
    TURN_START_MIN_SHARE,
    count_history_tokens,
    count_tail_tokens,
    split_history,
)


class DummyLimiter(LLMLimiter):
    def count_tokens(self, obj) -> int:
        if isinstance(obj, list):
            return sum(self.count_tokens(x) for x in obj)
        return 1

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text


@pytest.fixture
def limiter():
    return DummyLimiter()


def test_split_history_near_window(limiter):
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(10)]

    to_sum, to_keep = split_history(messages, 3, limiter, 100)
    assert len(to_keep) == 3

    to_sum, to_keep = split_history(messages, 3, limiter, 2)
    assert len(to_keep) == 1


def test_split_history_falls_back_to_the_looser_budget(limiter):
    """When even the newest message alone breaks the tight tail budget, a
    second attempt against `FALLBACK_BUDGET_RATIO` still keeps something."""
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(5)]
    # 1 token/message: tight tail budget is 0.8 (nothing fits), loose is 1.6.
    threshold = 2

    to_sum, to_keep = split_history(messages, 0, limiter, threshold)

    assert len(to_keep) > 0
    assert to_sum + to_keep == messages


def test_split_history_keeps_nothing_when_even_the_loose_budget_cannot_fit():
    """A single message bigger than `FALLBACK_BUDGET_RATIO` of the threshold
    is summarized, not kept — there is no third, looser tier."""
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(5)]

    class HugeLastMessageLimiter(LLMLimiter):
        def count_tokens(self, obj) -> int:
            if not isinstance(obj, list):
                return 1
            return sum(1000 if m is messages[-1] else 1 for m in obj)

        def truncate_text(self, text: str, max_tokens: int) -> str:
            return text

    to_sum, to_keep = split_history(messages, 0, HugeLastMessageLimiter(), 10)

    assert to_keep == []
    assert to_sum == messages


class _CallCounter:
    """A limiter's public counter, counting its own calls.

    Assigned over `limiter.<name>` on the instance, so the splitter keeps
    seeing an instance of its own class (the shortcut's gate reads the type) and
    the counting wraps the real counter rather than replacing it. *name* is the
    measurement under test: `count_tail_tokens` asks the shipped limiter for
    `count_content_tokens`, and a subclass for `count_tokens`.
    """

    def __init__(self, limiter: LLMLimiter, name: str) -> None:
        self._measure = getattr(limiter, name)
        self.total = 0

    def __call__(self, content) -> int:
        self.total += 1
        return self._measure(content)


class _SpikyLimiter(LLMLimiter):
    """A subclass whose suffix counts rise in the middle of the history.

    10 tokens per message, except a suffix that opens on a system prompt: 200.
    On `_spiky_history()` that makes index 3 the first suffix under a 50-token
    budget, while a bisection probes index 4 (200, over budget) and settles on
    index 5 — so a subclass served by the bisected scan would split elsewhere.
    """

    def count_tokens(self, content) -> int:
        if not isinstance(content, list):
            return 10
        parts = getattr(content[0], "parts", [])
        if any(isinstance(part, SystemPromptPart) for part in parts):
            return 200
        return 10 * len(content)


def _plain_history(size: int) -> list:
    """A history with no turn starts, so every index lands past the turn-start check."""
    messages = []
    for index in range(size):
        if index % 2 == 0:
            messages.append(ModelResponse(parts=[TextPart(content="x" * 40)]))
        else:
            messages.append(ModelRequest(parts=[SystemPromptPart(content="y" * 40)]))
    return messages


def _spiky_history() -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content="u")]),
        ModelResponse(parts=[TextPart(content="t")]),
        ModelResponse(parts=[TextPart(content="t")]),
        ModelResponse(parts=[TextPart(content="t")]),
        ModelRequest(parts=[SystemPromptPart(content="s")]),
        ModelResponse(parts=[TextPart(content="t")]),
        ModelResponse(parts=[TextPart(content="t")]),
        ModelResponse(parts=[TextPart(content="t")]),
    ]


def _only_newest_fits(limiter: LLMLimiter, messages: list) -> int:
    """A threshold whose tail budget only the newest message fits.

    Measured with `count_tail_tokens`, the currency the split itself uses: the
    rendered form is larger than the messages, so a threshold derived from the
    raw count would fit nothing and send the split to its retry budget.
    """
    return int(count_tail_tokens(limiter, messages[-1:]) / TAIL_BUDGET_RATIO) + 1


def _random_history(rng: random.Random, with_anchors: bool, size: int) -> list:
    """A history mixing turns, tool pairs, dangling calls and orphan returns."""
    messages = []
    call_id = 0
    while len(messages) < size:
        body = "".join(rng.choice("abcdefghij ") for _ in range(rng.randint(0, 40)))
        roll = rng.random()
        if roll < 0.3:
            messages.append(
                ModelRequest(
                    parts=[UserPromptPart(content=body)],
                    instructions=body if rng.random() < 0.3 else None,
                )
            )
        elif roll < 0.5:
            messages.append(ModelResponse(parts=[TextPart(content=body)]))
        elif roll < 0.65:
            call_id += 1
            messages.append(
                ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name="t", args={"a": body}, tool_call_id=f"c{call_id}"
                        )
                    ]
                )
            )
            if rng.random() < 0.7:
                messages.append(
                    ModelRequest(
                        parts=[
                            ToolReturnPart(
                                tool_name="t", content=body, tool_call_id=f"c{call_id}"
                            )
                        ]
                    )
                )
        elif roll < 0.8:
            messages.append(
                ModelRequest(
                    parts=[
                        ToolReturnPart(tool_name="t", content=body, tool_call_id="x")
                    ]
                )
            )
        else:
            messages.append(
                ModelResponse(
                    parts=[TextPart(content=body)],
                    usage=(
                        RequestUsage(input_tokens=rng.randint(1, 300), output_tokens=5)
                        if with_anchors and rng.random() < 0.5
                        else RequestUsage()
                    ),
                )
            )
    return messages[:size]


def _thresholds(rng: random.Random, limiter: LLMLimiter, messages: list) -> list:
    """Thresholds spanning no fit at all through keeping the whole history."""
    total = max(1, count_history_tokens(limiter, messages))
    return [1, total // 8, total // 3, total // 2, total, total * 2, total * 8]


def _linear_budget_split(messages, limiter, budget):
    """The pre-shortcut scan: the earliest split whose tail fits, counting each.

    Verbatim from the code the bisected scan replaced, kept as the oracle — with
    the measurement the splitter makes (`count_tail_tokens`), so an anchor on
    the newest response cannot make the two disagree about what fits.
    Returns `len(messages)` (keep nothing) rather than ``None`` when nothing
    fits, matching `_earliest_split_within_budget`'s own contract.
    """
    first_fit = None
    for split_idx in range(1, len(messages)):
        tail_tokens = count_tail_tokens(limiter, messages[split_idx:])
        if tail_tokens > budget:
            continue
        if first_fit is None:
            first_fit = split_idx
        if is_turn_start(messages[split_idx]):
            if tail_tokens >= budget * TURN_START_MIN_SHARE:
                return split_idx
            break
    return first_fit if first_fit is not None else len(messages)


def _reference_split_history(messages, summary_window, limiter, threshold):
    """`split_history` as it stood before the bisected scan, end to end.

    The oracle for the differential tests: the same algorithm, with the
    budget scan counting every candidate in order instead of bisecting.
    """
    if not messages:
        return [], []
    budget = threshold * TAIL_BUDGET_RATIO
    if count_history_tokens(limiter, messages) <= budget:
        split_idx = 0
    else:
        split_idx = _linear_budget_split(messages, limiter, budget)
    if split_idx == len(messages):
        loose_budget = threshold * FALLBACK_BUDGET_RATIO
        if loose_budget > budget:
            split_idx = _linear_budget_split(messages, limiter, loose_budget)
    count_cap = max(0, len(messages) - summary_window) if summary_window > 0 else 0
    split_idx = min(max(split_idx, count_cap), len(messages))
    if split_idx == 0:
        return [], list(messages)
    return messages[:split_idx], messages[split_idx:]


def test_the_default_limiter_bisects_for_its_first_fitting_split():
    """80 candidates cost a handful of counts, and the split is the old one."""
    messages = _plain_history(80)
    limiter = LLMLimiter()
    threshold = _only_newest_fits(limiter, messages)
    expected = _reference_split_history(messages, 0, limiter, threshold)

    counter = _CallCounter(limiter, "count_content_tokens")
    setattr(limiter, "count_content_tokens", counter)
    split = split_history(messages, 0, limiter, threshold)

    assert split == expected
    assert counter.total > 0, "the counter never ran: this test measures nothing"
    assert counter.total <= 2 * len(messages).bit_length()
    assert counter.total < len(messages)


def test_a_subclass_limiter_keeps_the_linear_scan():
    """A counting subclass is walked candidate by candidate, not bisected.

    Its counts are not monotone, so the shortcut's precondition does not hold —
    and the answer is index 3, the one every-candidate-in-order finds.
    """
    messages = _spiky_history()
    limiter = _SpikyLimiter()
    threshold = 125  # tail budget 50: index 3 fits, indices 1 and 2 do not

    counter = _CallCounter(limiter, "count_tokens")
    limiter.count_tokens = counter
    to_summarize, to_keep = split_history(messages, 0, limiter, threshold)

    assert (len(to_summarize), len(to_keep)) == (3, 5)
    assert counter.total == len(messages)


def test_tiktoken_keeps_the_linear_scan(monkeypatch):
    """BPE re-tokenizes across the dropped boundary, so it is walked too."""
    monkeypatch.setattr(CFG, "ENABLE_TIKTOKEN", True, raising=False)
    messages = _plain_history(40)
    limiter = LLMLimiter()
    threshold = _only_newest_fits(limiter, messages)
    expected = _reference_split_history(messages, 0, limiter, threshold)

    counter = _CallCounter(limiter, "count_content_tokens")
    setattr(limiter, "count_content_tokens", counter)
    split = split_history(messages, 0, limiter, threshold)

    assert split == expected
    assert counter.total == len(messages)


@pytest.mark.parametrize("with_anchors", [False, True])
def test_the_default_limiter_never_counts_a_shorter_suffix_higher(with_anchors):
    """The shortcut's precondition, stated as a test: counts fall as tails shrink.

    Counted the way the split counts — the rendered tail, `count_tail_tokens` —
    not the raw messages: bisecting on one currency and fitting on another is
    how a tail gets chosen that does not actually fit.
    """
    rng = random.Random(6006 + int(with_anchors))
    limiter = LLMLimiter()
    for _ in range(40):
        messages = _random_history(rng, with_anchors, rng.randint(2, 20))
        counts = [count_tail_tokens(limiter, messages[i:]) for i in range(len(messages))]
        assert counts == sorted(counts, reverse=True)


@pytest.mark.parametrize("with_anchors", [False, True])
@pytest.mark.parametrize("limiter_kind", ["default", "subclass"])
def test_split_history_matches_the_pre_shortcut_algorithm(limiter_kind, with_anchors):
    """Randomized differential: same split as the linear oracle, every time.

    Both limiter kinds and anchored or plain histories, because the shortcut
    and the walk have to agree on the anchored case too: a usage anchor pins
    the count for every suffix that still holds it.
    """
    rng = random.Random(3105 + int(with_anchors) + 7 * (limiter_kind == "subclass"))
    limiter = LLMLimiter() if limiter_kind == "default" else DummyLimiter()
    for _ in range(10):
        messages = _random_history(rng, with_anchors, rng.randint(2, 18))
        summary_window = rng.choice([0, 0, 2, len(messages)])
        for threshold in _thresholds(rng, limiter, messages):
            assert split_history(
                messages, summary_window, limiter, threshold
            ) == _reference_split_history(messages, summary_window, limiter, threshold)


def test_a_suffix_counting_exactly_the_budget_still_fits():
    """The fit test is `tail <= budget`: a tail equal to it is kept, not skipped.

    Twelve identical messages, and a threshold whose tail budget is exactly the
    rendered size of the last five: that suffix fits on the boundary, so index 7
    is the split to keep. A strict comparison would settle on index 8 instead.
    """
    messages = [
        ModelResponse(parts=[TextPart(content=f"{index:02d}" * 20)])
        for index in range(12)
    ]
    limiter = LLMLimiter()
    tail = count_tail_tokens(limiter, messages[7:])
    threshold = tail / TAIL_BUDGET_RATIO

    # Exact, not approximate: a float hair under `tail` would let the boundary
    # case pass for the wrong reason.
    assert threshold * TAIL_BUDGET_RATIO == tail
    assert count_tail_tokens(limiter, messages) > threshold * TAIL_BUDGET_RATIO
    assert count_tail_tokens(limiter, messages[6:]) > threshold * TAIL_BUDGET_RATIO

    to_summarize, to_keep = split_history(messages, 0, limiter, threshold)

    assert (len(to_summarize), len(to_keep)) == (7, 5)
    assert (to_summarize, to_keep) == _reference_split_history(
        messages, 0, limiter, threshold
    )


def test_the_absolute_ceiling_shrinks_the_tail(limiter):
    """A share of a large window is still a lot of transcript, so the ceiling
    wins when it is the smaller of the two: the ratio alone would keep all 40
    one-token messages here, the ceiling keeps 10."""
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(40)]

    to_summarize, to_keep = split_history(messages, 0, limiter, 100, tail_max_tokens=10)

    assert len(to_keep) == 10
    assert to_summarize == messages[:30]


def test_a_ceiling_above_the_budget_changes_nothing(limiter):
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(10)]

    without_ceiling = split_history(messages, 0, limiter, 100)
    with_ceiling = split_history(messages, 0, limiter, 100, tail_max_tokens=10_000)

    assert with_ceiling == without_ceiling


def test_a_ceiling_of_zero_means_no_ceiling(limiter):
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(40)]

    assert split_history(
        messages, 0, limiter, 100, tail_max_tokens=0
    ) == split_history(messages, 0, limiter, 100)


class _CharLimiter(LLMLimiter):
    """One token per character, so a message can be given a size in a test."""

    def count_tokens(self, content) -> int:
        return len(str(content))

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text[:max_tokens]


def test_a_message_over_the_ceiling_is_summarized_rather_than_kept():
    """The ceiling bounds the retry too, and that is the trade it makes.

    Without a ceiling the loose retry budget (0.8 of the threshold) is wide
    enough to keep a message that the tight 0.4 budget could not; with one, both
    budgets are capped to the same number, so a newest message over the ceiling
    is summarized instead of being kept whole.
    """
    limiter = _CharLimiter()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="x" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="x" * 50)]),
        ModelRequest(parts=[UserPromptPart(content="x" * 500)]),
    ]
    threshold = 2_000

    uncapped = split_history(messages, 0, limiter, threshold)
    capped = split_history(messages, 0, limiter, threshold, tail_max_tokens=100)

    assert len(uncapped[1]) == 1  # the 500-character message, kept by the retry
    assert capped[1] == []


def _history_with_whole_history_usage(size: int, usage_tokens: int) -> list:
    """Alternating request/response messages, the newest carrying a usage count.

    *usage_tokens* is what a provider reports on the last response at
    compaction time: the input of the request that produced it, which carried
    the whole history.
    """
    messages = []
    for index in range(size):
        body = "x" * 400
        if index % 2 == 0:
            messages.append(ModelRequest(parts=[UserPromptPart(content=body)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=body)]))
    messages[-1] = ModelResponse(
        parts=[TextPart(content="x" * 400)],
        usage=RequestUsage(input_tokens=usage_tokens, output_tokens=10),
    )
    return messages


def test_a_usage_anchor_does_not_zero_the_tail():
    """A compaction must keep a verbatim tail even though the newest response
    reports the whole history's input tokens.

    That report is the request the provider charged for, so it covers every
    message before it; read as the size of a *suffix* it means no suffix ever
    fits a budget that the history itself exceeded, and every compaction
    replaced everything with its summary. On a real 414-message history that
    was keep 0 versus keep 62 messages / 23,977 tokens.
    """
    limiter = LLMLimiter()
    messages = _history_with_whole_history_usage(12, usage_tokens=100_000)
    threshold = 2_000  # tail budget 800: about eight of these messages

    to_summarize, to_keep = split_history(messages, 0, limiter, threshold)

    assert to_keep, "compaction kept nothing, so only the summary would resume it"
    assert to_summarize + to_keep == messages
    assert limiter.count_content_tokens(to_keep) <= threshold * TAIL_BUDGET_RATIO


def test_the_content_measure_ignores_a_usage_anchor():
    """The anchor answers "what did this request cost", not "how big is this"."""
    limiter = LLMLimiter()
    anchored = _history_with_whole_history_usage(2, usage_tokens=100_000)

    assert limiter.count_tokens(anchored) > 100_000
    assert limiter.count_content_tokens(anchored) < 1_000
