import time
from unittest.mock import MagicMock

import jwt as pyjwt
import pytest

from zrb.builtin.jwt import decode_jwt, encode_jwt, validate_jwt
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


@pytest.fixture
def session():
    return Session(shared_ctx=SharedContext(), state_logger=MagicMock())


@pytest.mark.asyncio
async def test_encode_jwt(session):
    token = await encode_jwt.async_run(
        session=session,
        kwargs={
            "secret": "secret",
            "payload": '{"foo": "bar"}',
            "algorithm": "HS256",
        },
    )
    assert isinstance(token, str)


@pytest.mark.asyncio
async def test_decode_jwt():
    s1 = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
    token = await encode_jwt.async_run(
        session=s1,
        kwargs={
            "secret": "secret",
            "payload": '{"foo": "bar"}',
            "algorithm": "HS256",
        },
    )

    s2 = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
    payload = await decode_jwt.async_run(
        session=s2, kwargs={"token": token, "secret": "secret", "algorithm": "HS256"}
    )
    assert payload == {"foo": "bar"}


@pytest.mark.asyncio
async def test_validate_jwt():
    secret = "secret"
    algorithm = "HS256"
    token = pyjwt.encode({"exp": time.time() + 3600}, secret, algorithm=algorithm)

    # Valid
    s1 = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
    res1 = await validate_jwt.async_run(
        session=s1,
        kwargs={"token": token, "secret": secret, "algorithm": algorithm},
    )
    assert res1 is True

    # Expired
    s2 = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
    expired_token = pyjwt.encode(
        {"exp": time.time() - 3600}, secret, algorithm=algorithm
    )
    res2 = await validate_jwt.async_run(
        session=s2,
        kwargs={"token": expired_token, "secret": secret, "algorithm": algorithm},
    )
    assert res2 is False
