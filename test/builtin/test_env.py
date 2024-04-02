from zrb.builtin.env import get_env


def test_get():
    function = get_env.to_function()
    result = function()
    assert len(result.keys()) > 0
