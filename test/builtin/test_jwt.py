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


class TestJwtErrorHandling:
    """Test error handling in JWT functions through public API."""

    @pytest.mark.asyncio
    async def test_encode_jwt_invalid_json(self, session):
        """Test encode_jwt with invalid JSON payload."""
        with pytest.raises(Exception):
            await encode_jwt.async_run(
                session=session,
                kwargs={
                    "secret": "secret",
                    "payload": "not valid json",
                    "algorithm": "HS256",
                },
            )

    @pytest.mark.asyncio
    async def test_decode_jwt_invalid_token(self):
        """Test decode_jwt with invalid token."""
        session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
        with pytest.raises(Exception):
            await decode_jwt.async_run(
                session=session,
                kwargs={
                    "token": "invalid.token.here",
                    "secret": "secret",
                    "algorithm": "HS256",
                },
            )

    @pytest.mark.asyncio
    async def test_decode_jwt_wrong_secret(self):
        """Test decode_jwt with wrong secret."""
        session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
        token = pyjwt.encode({"foo": "bar"}, "correct_secret", algorithm="HS256")
        with pytest.raises(Exception):
            await decode_jwt.async_run(
                session=session,
                kwargs={
                    "token": token,
                    "secret": "wrong_secret",
                    "algorithm": "HS256",
                },
            )

    @pytest.mark.asyncio
    async def test_validate_jwt_invalid_token(self):
        """Test validate_jwt with completely invalid token."""
        session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
        result = await validate_jwt.async_run(
            session=session,
            kwargs={
                "token": "not-a-valid-jwt",
                "secret": "secret",
                "algorithm": "HS256",
            },
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_jwt_wrong_secret(self):
        """Test validate_jwt with wrong secret."""
        session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
        token = pyjwt.encode({"foo": "bar"}, "correct_secret", algorithm="HS256")
        result = await validate_jwt.async_run(
            session=session,
            kwargs={
                "token": token,
                "secret": "wrong_secret",
                "algorithm": "HS256",
            },
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_encode_jwt_different_algorithms(self):
        """Test encode_jwt with different algorithms."""
        for algorithm in ["HS256", "HS384", "HS512"]:
            session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
            token = await encode_jwt.async_run(
                session=session,
                kwargs={
                    "secret": "secret",
                    "payload": '{"test": "value"}',
                    "algorithm": algorithm,
                },
            )
            assert isinstance(token, str)
            # Verify we can decode it
            decoded = pyjwt.decode(token, "secret", algorithms=[algorithm])
            assert decoded == {"test": "value"}

    @pytest.mark.asyncio
    async def test_decode_jwt_expired_token(self):
        """Test decode_jwt with expired token."""
        session = Session(shared_ctx=SharedContext(), state_logger=MagicMock())
        # Create an expired token
        expired_token = pyjwt.encode(
            {"exp": time.time() - 3600}, "secret", algorithm="HS256"
        )
        with pytest.raises(Exception):
            await decode_jwt.async_run(
                session=session,
                kwargs={
                    "token": expired_token,
                    "secret": "secret",
                    "algorithm": "HS256",
                },
            )
