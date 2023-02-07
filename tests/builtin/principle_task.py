from zrb.builtin.principle_task import (
    principle_show_dry, principle_show_kiss, principle_show_pancasila,
    principle_show_solid, principle_show_yagni
)


def test_principle_show_dry():
    main_loop = principle_show_dry.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_kiss_show():
    main_loop = principle_show_kiss.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_pancasila_show():
    main_loop = principle_show_pancasila.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_solid_show():
    main_loop = principle_show_solid.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_yagni_show():
    main_loop = principle_show_yagni.create_main_loop()
    result = main_loop()
    assert result is None
