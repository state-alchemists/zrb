from zrb.builtin.env import (
    show_task, get_task
)


def test_env_show():
    main_loop = show_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_env_get():
    main_loop = get_task.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
