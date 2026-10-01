import pytest

from zrb.llm.stream_observer import create_observed_event_handler


@pytest.mark.asyncio
async def test_no_observers_returns_the_handler_itself():
    async def handler(event):
        pass

    assert create_observed_event_handler(handler, None) is handler
    assert create_observed_event_handler(handler, []) is handler
    assert create_observed_event_handler(None, []) is None


@pytest.mark.asyncio
async def test_observers_see_each_event_after_the_handler():
    seen = []

    async def handler(event):
        seen.append(("handler", event))

    async def async_observer(event):
        seen.append(("async", event))

    handle = create_observed_event_handler(
        handler, [lambda event: seen.append(("sync", event)), async_observer]
    )
    await handle("e1")

    assert seen == [("handler", "e1"), ("sync", "e1"), ("async", "e1")]


@pytest.mark.asyncio
async def test_observers_work_without_a_handler():
    seen = []
    handle = create_observed_event_handler(None, [seen.append])
    await handle("e1")
    assert seen == ["e1"]


@pytest.mark.asyncio
async def test_a_failing_observer_is_skipped_not_raised(caplog):
    seen = []

    def broken(event):
        raise RuntimeError("boom")

    handle = create_observed_event_handler(None, [broken, seen.append])
    await handle("e1")

    assert seen == ["e1"]
    assert "boom" in caplog.text
