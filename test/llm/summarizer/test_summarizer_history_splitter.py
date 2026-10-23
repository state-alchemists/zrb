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
from zrb.llm.message import get_tool_pairs
from zrb.llm.summarizer.history_splitter import (
    TAIL_BUDGET_RATIO,
    TURN_START_MIN_SHARE,
    find_best_effort_split,
    find_safe_split_index,
    is_split_safe,
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


def test_is_split_safe_complete_pair():
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="a", content="done", tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="3")]),
    ]
    from zrb.llm.message import get_tool_pairs

    tool_pairs = get_tool_pairs(messages)

    assert is_split_safe(messages, 1, tool_pairs)

    assert not is_split_safe(messages, 2, tool_pairs)

    assert is_split_safe(messages, 3, tool_pairs)


def test_find_safe_split_index(limiter):
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="a", content="done", tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="3")]),
    ]

    idx = find_safe_split_index(messages, limiter, 100)
    assert idx == 3

    messages_no_turn_start = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="a", content="done", tool_call_id="1")]
        ),
        ModelResponse(parts=[ToolCallPart(tool_name="b", args={}, tool_call_id="2")]),
    ]
    idx_no_turn = find_safe_split_index(messages_no_turn_start, limiter, 100)
    assert idx_no_turn == 1

    idx = find_safe_split_index(messages, limiter, 2)
    assert idx == 3


def test_find_best_effort_split(limiter):
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(parts=[UserPromptPart(content="2")]),
    ]

    to_sum, to_keep = find_best_effort_split(messages, limiter, 100)

    assert len(to_sum) == 1
    assert len(to_keep) == 2


def test_split_history_near_window(limiter):
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(10)]

    to_sum, to_keep = split_history(messages, 3, limiter, 100)
    assert len(to_keep) == 3

    to_sum, to_keep = split_history(messages, 3, limiter, 2)
    assert len(to_keep) == 1


class _CallCounter:
    """A limiter's public counter, counting its own calls.

    Assigned over `limiter.count_tokens` on the instance, so the splitter keeps
    seeing an instance of its own class (the shortcut's gate reads the type) and
    the counting wraps the real counter rather than replacing it.
    """

    def __init__(self, limiter: LLMLimiter) -> None:
        self._count_tokens = limiter.count_tokens
        self.total = 0

    def __call__(self, content) -> int:
        self.total += 1
        return self._count_tokens(content)


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
    """A history with no turn starts and no tool pairs, so every index is safe."""
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
    """A threshold whose tail budget only the newest message fits."""
    return int(limiter.count_tokens(messages[-1:]) / TAIL_BUDGET_RATIO) + 1


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
    total = max(1, limiter.count_tokens(messages))
    return [1, total // 8, total // 3, total // 2, total, total * 2, total * 8]


def _linear_budget_split(messages, limiter, budget, tool_pairs):
    """The pre-shortcut scan: the earliest split whose tail fits, counting each.

    Verbatim from the code the bisected scan replaced, kept as the oracle.
    """
    first_safe = None
    for split_idx in range(1, len(messages)):
        tail_tokens = limiter.count_tokens(messages[split_idx:])
        if tail_tokens > budget:
            continue
        if not is_split_safe(messages, split_idx, tool_pairs):
            continue
        if first_safe is None:
            first_safe = split_idx
        if is_turn_start(messages[split_idx]):
            if tail_tokens >= budget * TURN_START_MIN_SHARE:
                return split_idx
            break
    return first_safe


def _linear_first_safe_from(messages, start, tool_pairs):
    """The pre-shortcut scan for the first safe split at or after *start*."""
    first_safe = None
    for split_idx in range(start, len(messages)):
        if not is_split_safe(messages, split_idx, tool_pairs):
            continue
        if first_safe is None:
            first_safe = split_idx
        if is_turn_start(messages[split_idx]):
            return split_idx
    return first_safe


def _reference_split_history(messages, summary_window, limiter, threshold):
    """`split_history` as it stood before the bisected scan, end to end.

    The oracle for the differential tests: the same algorithm, with both budget
    scans counting every candidate in order. `_fallback_split`'s last-resort
    backward walk is left out because a non-empty history never reaches it —
    `find_best_effort_split` always answers.
    """
    if not messages:
        return [], []
    tool_pairs = get_tool_pairs(messages)
    budget = threshold * TAIL_BUDGET_RATIO
    count_cap = max(0, len(messages) - summary_window) if summary_window > 0 else 0
    if limiter.count_tokens(messages) <= budget:
        budget_split = 0
    else:
        budget_split = _linear_budget_split(messages, limiter, budget, tool_pairs)
    if budget_split is None:
        fallback = find_safe_split_index(messages, limiter, threshold, tool_pairs)
        if fallback >= 0:
            return messages[:fallback], messages[fallback:]
        return find_best_effort_split(messages, limiter, threshold, tool_pairs)
    split_idx = budget_split
    if count_cap > split_idx:
        split_idx = (
            _linear_first_safe_from(messages, count_cap, tool_pairs) or split_idx
        )
    if split_idx == 0:
        return [], list(messages)
    return messages[:split_idx], messages[split_idx:]


def test_the_default_limiter_bisects_for_its_first_fitting_split():
    """80 candidates cost a handful of counts, and the split is the old one."""
    messages = _plain_history(80)
    limiter = LLMLimiter()
    threshold = _only_newest_fits(limiter, messages)
    expected = _reference_split_history(messages, 0, limiter, threshold)

    counter = _CallCounter(limiter)
    limiter.count_tokens = counter
    split = split_history(messages, 0, limiter, threshold)

    assert split == expected
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

    counter = _CallCounter(limiter)
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

    counter = _CallCounter(limiter)
    limiter.count_tokens = counter
    split = split_history(messages, 0, limiter, threshold)

    assert split == expected
    assert counter.total == len(messages)


@pytest.mark.parametrize("with_anchors", [False, True])
def test_the_default_limiter_never_counts_a_shorter_suffix_higher(with_anchors):
    """The shortcut's precondition, stated as a test: counts fall as tails shrink."""
    rng = random.Random(6006 + int(with_anchors))
    limiter = LLMLimiter()
    for _ in range(40):
        messages = _random_history(rng, with_anchors, rng.randint(2, 20))
        counts = [limiter.count_tokens(messages[i:]) for i in range(len(messages))]
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

    Twelve identical messages counting 10 tokens each, and a 125-token
    threshold whose tail budget is exactly 50.0: the suffix from index 7 counts
    precisely that, so index 7 is the split to keep. A strict comparison would
    settle on index 8 instead.
    """
    messages = [
        ModelResponse(parts=[TextPart(content=f"{index:02d}" * 20)])
        for index in range(12)
    ]
    limiter = LLMLimiter()
    threshold = 125

    assert limiter.count_tokens(messages) > threshold * TAIL_BUDGET_RATIO
    assert limiter.count_tokens(messages[7:]) == threshold * TAIL_BUDGET_RATIO
    assert limiter.count_tokens(messages[6:]) > threshold * TAIL_BUDGET_RATIO

    to_summarize, to_keep = split_history(messages, 0, limiter, threshold)

    assert (len(to_summarize), len(to_keep)) == (7, 5)
    assert (to_summarize, to_keep) == _reference_split_history(
        messages, 0, limiter, threshold
    )
