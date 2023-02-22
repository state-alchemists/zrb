from zrb.builtin.md5_task import md5_hash_task, md5_sum_task
import pathlib
import os


def test_md5_sum():
    dir_path = pathlib.Path(__file__).parent.absolute()
    main_loop = md5_sum_task.create_main_loop()
    result = main_loop(file=os.path.join(dir_path, 'md5_test_sum.txt'))
    assert result == '5f935c38df842258336f683502ac153d'


def test_md5_hash():
    main_loop = md5_hash_task.create_main_loop()
    result = main_loop(text='Philosopher Stone')
    assert result == '5f935c38df842258336f683502ac153d'
