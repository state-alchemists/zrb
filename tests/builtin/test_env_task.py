from zrb.builtin.env_task import (
    env_show_task, env_get_task
)


def test_env_show():
    main_loop = env_show_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_env_get():
    main_loop = env_get_task.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
