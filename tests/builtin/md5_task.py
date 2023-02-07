from zrb.builtin.md5_task import md5_hash, md5_sum


def test_md5_sum():
    main_loop = md5_sum.create_main_loop()
    result = main_loop(file='md5_test_sum.txt')
    assert result == 'fcfb5c9c57b94766999649250b4e1e3c'


def test_md5_hash():
    main_loop = md5_hash.create_main_loop()
    result = main_loop(text='Philosopher Stone')
    assert result == 'fcfb5c9c57b94766999649250b4e1e3c'
