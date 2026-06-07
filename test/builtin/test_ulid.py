from unittest.mock import MagicMock

import pytest
import ulid

from zrb.builtin.ulid import generate_ulid, validate_ulid
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=MagicMock())


@pytest.mark.asyncio
async def test_generate_ulid():
    res = await generate_ulid.async_run(session=get_session())
    assert res is not None
    assert len(res) == 26


@pytest.mark.asyncio
async def test_validate_ulid():
    u = ulid.new().str

    # Valid
    res1 = await validate_ulid.async_run(session=get_session(), kwargs={"id": u})
    assert res1 is True

    # Invalid
    res2 = await validate_ulid.async_run(
        session=get_session(), kwargs={"id": "invalid"}
    )
    assert res2 is False


@pytest.mark.asyncio
async def test_generate_ulid_uniqueness():
    """Generated ULIDs should be unique."""
    ids = set()
    for _ in range(100):
        res = await generate_ulid.async_run(session=get_session())
        ids.add(res)
    assert len(ids) == 100
