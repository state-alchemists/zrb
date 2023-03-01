from zrb.builtin.principle import (
    show_dry_principle, show_kiss_principle,
    show_solid_principle, show_yagni_principle
)


def test_show_dry_principle():
    main_loop = show_dry_principle.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_kiss_principle():
    main_loop = show_kiss_principle.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_solid_principle():
    main_loop = show_solid_principle.create_main_loop()
    result = main_loop()
    assert result is None


def test_show_yagni_principle():
    main_loop = show_yagni_principle.create_main_loop()
    result = main_loop()
    assert result is None
