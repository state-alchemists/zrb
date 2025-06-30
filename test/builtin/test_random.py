from zrb.builtin.random import shuffle_values, throw_dice
from zrb.task.base_task import BaseTask


def test_throw_dice():
    task: BaseTask = throw_dice
    result = task.run(str_kwargs={"side": "6", "num-rolls": "1"})
    assert 1 <= int(result) <= 6


def test_shuffle():
    task: BaseTask = shuffle_values
    values = "a,b,c"
    result = task.run(str_kwargs={"values": values})
    result_list = result.split("\n")
    assert len(result_list) == 3
    assert "a" in result_list
    assert "b" in result_list
    assert "c" in result_list
