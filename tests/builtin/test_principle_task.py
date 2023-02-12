from zrb.builtin.principle_task import (
    principle_show_dry_task, principle_show_kiss_task, principle_show_pancasila_task,
    principle_show_solid_task, principle_show_yagni_task
)


def test_principle_show_dry():
    main_loop = principle_show_dry_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_kiss_show():
    main_loop = principle_show_kiss_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_pancasila_show():
    main_loop = principle_show_pancasila_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_solid_show():
    main_loop = principle_show_solid_task.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_yagni_show():
    main_loop = principle_show_yagni_task.create_main_loop()
    result = main_loop()
    assert result is None
