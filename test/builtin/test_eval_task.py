from zrb.builtin.eval_task import eval_task


def test_eval():
    main_loop = eval_task.create_main_loop()
    result = main_loop(expression='1+1')
    assert result == 2
