from zrb.builtin.principle import (
    principle_show_dry, principle_show_kiss, principle_show_pancasila,
    principle_show_solid, principle_show_yagni
)


def test_show_dry_principle():
    main_loop = principle_show_dry.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_kiss_principle():
    main_loop = principle_show_kiss.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_pancasila():
    main_loop = principle_show_pancasila.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_solid_principle():
    main_loop = principle_show_solid.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_yagni_principle():
    main_loop = principle_show_yagni.create_main_loop()
    result = main_loop()
    assert result is None
