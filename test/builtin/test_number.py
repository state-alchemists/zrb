from unittest import mock

import pytest

from zrb.builtin.number import convert_base
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.parametrize(
    "value, from_base, to_base, expected",
    [
        ("255", "10", "16", "ff"),
        ("ff", "16", "10", "255"),
        ("10", "2", "10", "2"),
        ("255", "10", "2", "11111111"),
        ("777", "8", "16", "1ff"),
    ],
)
@pytest.mark.asyncio
async def test_convert_base(value, from_base, to_base, expected):
    res = await convert_base.async_run(
        session=get_session(),
        kwargs={"value": value, "from_base": from_base, "to_base": to_base},
    )
    assert res == expected


@pytest.mark.asyncio
async def test_convert_base_invalid_value_raises_clear_error():
    with pytest.raises(ValueError, match="not a valid base-10 number"):
        await convert_base.async_run(
            session=get_session(),
            kwargs={"value": "xyz", "from_base": "10", "to_base": "16"},
        )
