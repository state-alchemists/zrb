import uuid
from unittest.mock import MagicMock

import pytest

from zrb.builtin.uuid import (
    generate_uuid_v1,
    generate_uuid_v3,
    generate_uuid_v4,
    generate_uuid_v5,
    validate_uuid,
    validate_uuid_v1,
    validate_uuid_v3,
    validate_uuid_v4,
    validate_uuid_v5,
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


@pytest.mark.asyncio
async def test_validate_uuid_v1():
    """Test validate_uuid_v1 function."""
    # Valid UUID v1
    u1 = str(uuid.uuid1())
    res1 = await validate_uuid_v1.async_run(session=get_session(), kwargs={"id": u1})
    assert res1 is True

    # Invalid UUID
    res2 = await validate_uuid_v1.async_run(
        session=get_session(), kwargs={"id": "invalid"}
    )
    assert res2 is False


@pytest.mark.asyncio
async def test_validate_uuid_v3():
    """Test validate_uuid_v3 function."""
    # Valid UUID v3
    u3 = str(uuid.uuid3(uuid.NAMESPACE_DNS, "example.com"))
    res1 = await validate_uuid_v3.async_run(session=get_session(), kwargs={"id": u3})
    assert res1 is True

    # Invalid UUID
    res2 = await validate_uuid_v3.async_run(
        session=get_session(), kwargs={"id": "invalid"}
    )
    assert res2 is False


@pytest.mark.asyncio
async def test_validate_uuid_v4():
    """Test validate_uuid_v4 function."""
    # Valid UUID v4
    u4 = str(uuid.uuid4())
    res1 = await validate_uuid_v4.async_run(session=get_session(), kwargs={"id": u4})
    assert res1 is True

    # Invalid UUID
    res2 = await validate_uuid_v4.async_run(
        session=get_session(), kwargs={"id": "invalid"}
    )
    assert res2 is False


@pytest.mark.asyncio
async def test_validate_uuid_v5():
    """Test validate_uuid_v5 function."""
    # Valid UUID v5
    u5 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))
    res1 = await validate_uuid_v5.async_run(session=get_session(), kwargs={"id": u5})
    assert res1 is True

    # Invalid UUID
    res2 = await validate_uuid_v5.async_run(
        session=get_session(), kwargs={"id": "invalid"}
    )
    assert res2 is False


@pytest.mark.asyncio
async def test_generate_uuid_v1_with_params():
    """Test generate_uuid_v1 with custom node and clock_seq."""
    res = await generate_uuid_v1.async_run(
        session=get_session(),
        kwargs={"node": "123456789012", "clock_seq": "1234"},
    )
    assert res is not None
    assert len(str(res)) > 30


@pytest.mark.asyncio
async def test_generate_uuid_v3_all_namespaces():
    """Test generate_uuid_v3 with all namespace options."""
    for ns in ["dns", "url", "oid", "x500"]:
        res = await generate_uuid_v3.async_run(
            session=get_session(), kwargs={"namespace": ns, "name": "test"}
        )
        assert res is not None
        assert len(str(res)) > 30


@pytest.mark.asyncio
async def test_generate_uuid_v5_all_namespaces():
    """Test generate_uuid_v5 with all namespace options."""
    for ns in ["dns", "url", "oid", "x500"]:
        res = await generate_uuid_v5.async_run(
            session=get_session(), kwargs={"namespace": ns, "name": "test"}
        )
        assert res is not None
        assert len(str(res)) > 30
