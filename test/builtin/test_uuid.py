import uuid
from unittest.mock import MagicMock

import pytest

from zrb.builtin.uuid import (
    generate_uuid_v1,
    generate_uuid_v3,
    generate_uuid_v4,
    generate_uuid_v5,
    validate_uuid,
)
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=MagicMock())


@pytest.mark.asyncio
async def test_generate_uuids():
    # Test generation consistency
    for task in [generate_uuid_v1, generate_uuid_v4]:
        res = await task.async_run(session=get_session())
        assert res is not None
        assert len(str(res)) > 30

    # Test namespaced generation
    for task in [generate_uuid_v3, generate_uuid_v5]:
        res = await task.async_run(
            session=get_session(), kwargs={"namespace": "dns", "name": "example.com"}
        )
        assert res is not None
        assert len(str(res)) > 30


@pytest.mark.asyncio
async def test_validate_uuid():
    u4 = str(uuid.uuid4())
    # Valid
    res1 = await validate_uuid.async_run(session=get_session(), kwargs={"id": u4})
    assert res1 is True

    # Invalid
    res2 = await validate_uuid.async_run(
        session=get_session(), kwargs={"id": "invalid"}
    )
    assert res2 is False
