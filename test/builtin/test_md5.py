from zrb.builtin.md5 import hash_text, sum_file
import pathlib
import os


def test_sum_file():
    dir_path = pathlib.Path(__file__).parent.absolute()
    function = sum_file.to_function()
    result = function(file=os.path.join(dir_path, 'md5_test_sum.txt'))
    assert result == '5f935c38df842258336f683502ac153d'


def test_hash_text():
    function = hash_text.to_function()
    result = function(text='Philosopher Stone')
    assert result == '5f935c38df842258336f683502ac153d'
