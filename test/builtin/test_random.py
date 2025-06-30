import unittest
from unittest.mock import patch

from zrb.builtin.random import shuffle_values, throw_dice
from zrb.task.base_task import BaseTask


class TestBuiltinRandom(unittest.TestCase):
    def test_throw_dice(self):
        task: BaseTask = throw_dice
        result = task.run(str_kwargs={"side": "6", "num-rolls": "1"})
        self.assertTrue(1 <= int(result) <= 6)

    def test_shuffle(self):
        task: BaseTask = shuffle_values
        values = "a,b,c"
        result = task.run(str_kwargs={"values": values})
        result_list = result.split("\n")
        self.assertEqual(len(result_list), 3)
        self.assertIn("a", result_list)
        self.assertIn("b", result_list)
        self.assertIn("c", result_list)


if __name__ == "__main__":
    unittest.main()
