from zrb.builtin.env import (
    show, get
)


def test_show():
    main_loop = show.create_main_loop()
    result = main_loop()
    assert result is None


def test_get():
    main_loop = get.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
