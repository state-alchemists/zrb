from zrb.builtin.env_task import (
    env_show, env_get
)


def test_env_show():
    main_loop = env_show.create_main_loop()
    result = main_loop()
    assert result is None


def test_env_get():
    main_loop = env_get.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
