from zrb.builtin.md5 import hash_text, sum_file
import pathlib
import os


def test_sum_file():
    dir_path = pathlib.Path(__file__).parent.absolute()
    main_loop = sum_file.create_main_loop()
    result = main_loop(file=os.path.join(dir_path, 'md5_test_sum.txt'))
    assert result == '5f935c38df842258336f683502ac153d'


def test_hash_text():
    main_loop = hash_text.create_main_loop()
    result = main_loop(text='Philosopher Stone')
    assert result == '5f935c38df842258336f683502ac153d'
