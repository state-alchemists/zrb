from zrb.builtin.base64 import encode, decode


def test_encode():
    function = encode.to_function()
    result = function(text='Philosopher Stone')
    assert result == 'UGhpbG9zb3BoZXIgU3RvbmU='


def test_decode():
    function = decode.to_function()
    result = function(text='UGhpbG9zb3BoZXIgU3RvbmU=')
    assert result == 'Philosopher Stone'
