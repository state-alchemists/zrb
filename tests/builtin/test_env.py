from zrb.builtin.env import (
    show_env, get_env
)


def test_show_env():
    main_loop = show_env.create_main_loop()
    result = main_loop()
    assert result is None


def test_get_env():
    main_loop = get_env.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
