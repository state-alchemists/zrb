from zrb.builtin.eval import evaluate


def test_eval():
    main_loop = evaluate.create_main_loop()
    result = main_loop(expression='1+1')
    assert result == 2
