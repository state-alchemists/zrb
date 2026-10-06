'Tests for the rarely-hit branches in chunk_processor.'

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.summarizer.chunk_processor import chunk_and_summarize
from zrb.llm.util.capabilities import model_capabilities


class _Limiter:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


@pytest.mark.asyncio
async def test_empty_messages_returns_no_summaries_marker():
    """No messages → no chunks → fall through to the [No summaries] sentinel."""
    out = await chunk_and_summarize(
        messages=[],
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=100,
    )
    assert "[No summaries generated]" in out


@pytest.mark.asyncio
async def test_message_to_text_failure_falls_back_to_str():
    'If message_to_text raises, the converter falls back to str(m) and'
    with (
        patch(
            "zrb.llm.summarizer.chunk_processor.message_to_text",
            side_effect=RuntimeError("bad message shape"),
        ),
        patch(
            "zrb.llm.summarizer.chunk_processor.summarize_text_plain",
            new=AsyncMock(return_value="SUMMARY"),
        ),
    ):
        out = await chunk_and_summarize(
            messages=["msg one", "msg two"],
            agent=MagicMock(),
            limiter=_Limiter(),
            token_threshold=100,
        )
    assert "SUMMARY" in out





_TINY_MODEL = "zrb-test-tiny-window"
_TINY_WINDOW = 100


@pytest.fixture
def tiny_window_model():
    'A registered model whose window forces more than one chunk.'
    model_capabilities.register(_TINY_MODEL, context_window=_TINY_WINDOW)
    yield f"fake:{_TINY_MODEL}"
    model_capabilities.clear()


def _recording_summarizer(monkeypatch) -> list[str]:
    'Patch the summarizer seam and collect the text of every chunk it saw.'
    sent: list[str] = []

    async def fake_summarize(text, agent, limiter, threshold):
        sent.append(text)
        return "summary"

    monkeypatch.setattr(
        "zrb.llm.summarizer.chunk_processor.summarize_text_plain", fake_summarize
    )
    return sent


def _messages(words: int) -> list[str]:
    """Ten messages of *words* words each — `_Limiter` counts words as tokens."""
    return [" ".join(["w"] * words)] * 10


@pytest.mark.asyncio
async def test_chunk_is_capped_by_the_summarization_models_window(
    tiny_window_model, monkeypatch
):
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=_messages(80),
        agent=SimpleNamespace(model=tiny_window_model),
        limiter=_Limiter(),
        token_threshold=1000,
    )

    assert len(sent) > 1, "the request budget alone put the history in one chunk"
    assert all(
        _Limiter().count_tokens(chunk) <= int(_TINY_WINDOW * 0.9) for chunk in sent
    )


@pytest.mark.asyncio
async def test_chunk_uses_the_budget_when_the_model_window_is_unknown(monkeypatch):
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=_messages(80),
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=1000,
    )

    assert len(sent) == 1
    assert _Limiter().count_tokens(sent[0]) == 800
