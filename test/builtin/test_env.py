from zrb.builtin.env import get


def test_get():
    main_loop = get.create_main_loop()
    result = main_loop()
    assert len(result.keys()) > 0
