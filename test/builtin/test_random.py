import pytest
from unittest import mock
from zrb.builtin.random import shuffle_values, throw_dice
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session

def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())

@pytest.mark.asyncio
async def test_throw_dice():
    # 2 rolls * 2 dice = 4 randint calls
    with mock.patch("random.randint", side_effect=[3, 5, 1, 10]):
        res = await throw_dice.async_run(session=get_session(), kwargs={"side": "6, 20", "num_rolls": 2})
        assert "8" in str(res) # sum of first roll: 3+5
        assert "11" in str(res) # sum of second roll: 1+10

@pytest.mark.asyncio
async def test_shuffle_values():
    with mock.patch("random.shuffle") as mock_shuffle:
        def side_effect(num_list):
            num_list.reverse()
        mock_shuffle.side_effect = side_effect

        res = await shuffle_values.async_run(session=get_session(), kwargs={"values": "a, b, c"})
        assert res == "c\nb\na"
