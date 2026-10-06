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
    """Validate UUID version 1 values."""
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
    """Validate UUID version 3 values."""
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
async def test_validate_uuid_version_is_checked_not_rewritten():
    """A versioned validator must reject another version's UUID.

    `uuid.UUID(value, version=N)` *sets* the version bits, so before this the
    version-bearing check passed for every version.
    """
    u1 = str(uuid.uuid1())
    u3 = str(uuid.uuid3(uuid.NAMESPACE_DNS, "example.com"))
    u4 = str(uuid.uuid4())
    u5 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))
    versions = [
        (validate_uuid_v1, u1),
        (validate_uuid_v3, u3),
        (validate_uuid_v4, u4),
        (validate_uuid_v5, u5),
    ]
    for task, own in versions:
        assert await task.async_run(session=get_session(), kwargs={"id": own}) is True
        for other in (u1, u3, u4, u5):
            if other == own:
                continue
            assert (
                await task.async_run(session=get_session(), kwargs={"id": other})
                is False
            ), f"{task.name} accepted {other}"


@pytest.mark.asyncio
async def test_validate_uuid_accepts_any_version():
    """The unversioned validator is the "is this a UUID" one: every version."""
    for value in (
        str(uuid.uuid1()),
        str(uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")),
        str(uuid.uuid4()),
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")),
    ):
        assert await validate_uuid.async_run(
            session=get_session(), kwargs={"id": value}
        )


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
