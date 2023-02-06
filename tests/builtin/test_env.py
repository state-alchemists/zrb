from zrb.builtin.env import (
    env_show, env_get
)


def test_show_env():
    main_loop = env_show.create_main_loop()
    result = main_loop()
    assert result is None


def test_get_env():
    main_loop = env_get.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
