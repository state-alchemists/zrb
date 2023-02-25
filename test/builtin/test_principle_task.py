from zrb.builtin.principle import (
    show_dry_principle, show_kiss_principle, show_pancasila,
    show_solid_principle, show_yagni_principle
)


def test_principle_show_dry():
    main_loop = show_dry_principle.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_kiss_show():
    main_loop = show_kiss_principle.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_pancasila_show():
    main_loop = show_pancasila.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_solid_show():
    main_loop = show_solid_principle.create_main_loop()
    result = main_loop()
    assert result is None


def test_principle_yagni_show():
    main_loop = show_yagni_principle.create_main_loop()
    result = main_loop()
    assert result is None
