from zrb.builtin.principle import (
    show_dry_task, show_kiss_task, show_pancasila_task,
    show_solid_task, show_yagni_task
)


def test_principle_show_dry():
    main_loop = show_dry_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_kiss_show():
    main_loop = show_kiss_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_pancasila_show():
    main_loop = show_pancasila_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_solid_show():
    main_loop = show_solid_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_yagni_show():
    main_loop = show_yagni_task.create_main_loop()
    result = main_loop()
    assert result is None
