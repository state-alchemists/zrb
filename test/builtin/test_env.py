from zrb.builtin.env import get


def test_get():
    function = get.to_function()
    result = function()
    assert len(result.keys()) > 0
