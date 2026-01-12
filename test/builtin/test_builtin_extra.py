import time
from unittest import mock

import jwt
import pytest

from zrb.builtin import base64 as base64_module
from zrb.builtin import http as http_module
from zrb.builtin import jwt as jwt_module
from zrb.builtin import md5 as md5_module
from zrb.builtin import random as random_module
from zrb.builtin import uuid as uuid_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_throw_dice():
    task = random_module.throw_dice
    session = get_fresh_session()
    session.set_main_task(task)

    with mock.patch("random.randint", side_effect=[3, 15, 1, 10]):
        await task.async_run(session=session, kwargs={"side": "6, 20", "num_rolls": 2})
        log = "\n".join(session.shared_ctx.shared_log)
        # sums are 3+15=18 and 1+10=11.
        assert "18" in log
        assert "11" in log


@pytest.mark.asyncio
async def test_shuffle_values():
    task = random_module.shuffle_values
    session = get_fresh_session()
    session.set_main_task(task)

    with mock.patch("random.shuffle") as mock_shuffle:
        # Side effect to actually shuffle list in place
        def side_effect(num_list):
            num_list.reverse()

        mock_shuffle.side_effect = side_effect

        await task.async_run(session=session, kwargs={"values": "a, b, c"})
        result = session.final_result
        assert result == "c\nb\na"


@pytest.mark.asyncio
async def test_http_request():
    task = http_module.http_request
    session = get_fresh_session()
    session.set_main_task(task)

    # Mock requests.request
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_request.return_value = mock_response

        await task.async_run(
            session=session,
            kwargs={
                "url": "http://example.com",
                "method": "GET",
                "headers": '{"Content-Type": "application/json"}',
                "body": "{}",
                "timeout": 10,
                "verify_ssl": True,
            },
        )
        result = session.final_result
        assert result == mock_response
        mock_request.assert_called_with(
            method="GET",
            url="http://example.com",
            headers={"Content-Type": "application/json"},
            json=None,
            verify=True,
        )


@pytest.mark.asyncio
async def test_generate_curl():
    task = http_module.generate_curl
    session = get_fresh_session()
    session.set_main_task(task)

    await task.async_run(
        session=session,
        kwargs={
            "url": "http://example.com",
            "method": "POST",
            "headers": '{"Content-Type": "application/json"}',
            "body": '{"foo": "bar"}',
            "verify_ssl": True,
        },
    )
    result = session.final_result
    assert "curl -X POST" in result
    assert "http://example.com" in result
    assert "Content-Type: application/json" in result
    assert "-d" in result
    assert '{"foo": "bar"}' in result


@pytest.mark.asyncio
async def test_validate_base64():
    task = base64_module.validate_base64

    # True case
    session1 = get_fresh_session()
    session1.set_main_task(task)
    await task.async_run(session=session1, kwargs={"text": "aGVsbG8="})
    assert session1.final_result is True

    # False case
    session2 = get_fresh_session()
    session2.set_main_task(task)
    await task.async_run(session=session2, kwargs={"text": "invalid!!!"})
    assert session2.final_result is False


@pytest.mark.asyncio
async def test_validate_md5():
    task = md5_module.validate_md5

    # Valid MD5
    session1 = get_fresh_session()
    session1.set_main_task(task)
    await task.async_run(
        session=session1, kwargs={"hash": "d41d8cd98f00b204e9800998ecf8427e"}
    )
    assert session1.final_result is True

    # Invalid
    session2 = get_fresh_session()
    session2.set_main_task(task)
    await task.async_run(session=session2, kwargs={"hash": "invalid"})
    assert session2.final_result is False


@pytest.mark.asyncio
async def test_validate_jwt():
    task = jwt_module.validate_jwt
    secret = "secret"
    algorithm = "HS256"

    # Valid token
    session1 = get_fresh_session()
    session1.set_main_task(task)
    token = jwt.encode({"exp": time.time() + 3600}, secret, algorithm=algorithm)
    await task.async_run(
        session=session1,
        kwargs={"token": token, "secret": secret, "algorithm": algorithm},
    )
    assert session1.final_result is True

    # Expired token
    session2 = get_fresh_session()
    session2.set_main_task(task)
    token = jwt.encode({"exp": time.time() - 3600}, secret, algorithm=algorithm)
    await task.async_run(
        session=session2,
        kwargs={"token": token, "secret": secret, "algorithm": algorithm},
    )
    assert session2.final_result is False


@pytest.mark.asyncio
async def test_uuid_v3_v5_namespaces():
    # Test namespace mapping logic
    task_v3 = uuid_module.generate_uuid_v3
    session1 = get_fresh_session()
    session1.set_main_task(task_v3)
    await task_v3.async_run(
        session=session1, kwargs={"namespace": "dns", "name": "example.com"}
    )
    assert session1.final_result

    task_v5 = uuid_module.generate_uuid_v5
    session2 = get_fresh_session()
    session2.set_main_task(task_v5)
    await task_v5.async_run(
        session=session2, kwargs={"namespace": "dns", "name": "example.com"}
    )
    assert session2.final_result


@pytest.mark.asyncio
async def test_validate_uuid_versions():
    import uuid

    u1 = str(uuid.uuid1())
    u3 = str(uuid.uuid3(uuid.NAMESPACE_DNS, "test"))
    u4 = str(uuid.uuid4())
    u5 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test"))

    task_v1 = uuid_module.validate_uuid_v1
    session1 = get_fresh_session()
    session1.set_main_task(task_v1)
    await task_v1.async_run(session=session1, kwargs={"id": u1})
    assert session1.final_result is True

    task_v3 = uuid_module.validate_uuid_v3
    session2 = get_fresh_session()
    session2.set_main_task(task_v3)
    await task_v3.async_run(session=session2, kwargs={"id": u3})
    assert session2.final_result is True

    task_v4 = uuid_module.validate_uuid_v4
    session3 = get_fresh_session()
    session3.set_main_task(task_v4)
    await task_v4.async_run(session=session3, kwargs={"id": u4})
    assert session3.final_result is True

    task_v5 = uuid_module.validate_uuid_v5
    session4 = get_fresh_session()
    session4.set_main_task(task_v5)
    await task_v5.async_run(session=session4, kwargs={"id": u5})
    assert session4.final_result is True

    # Test invalid inputs
    task_v = uuid_module.validate_uuid
    session5 = get_fresh_session()
    session5.set_main_task(task_v)
    await task_v.async_run(session=session5, kwargs={"id": "invalid"})
    assert session5.final_result is False
