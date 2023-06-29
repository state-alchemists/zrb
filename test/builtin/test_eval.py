from zrb.builtin.eval import evaluate


def test_eval():
    function = evaluate.to_function()
    result = function(expression='1+1')
    assert result == 2
