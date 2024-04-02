from zrb.builtin.base64 import decode_base64, encode_base64


def test_encode():
    function = encode_base64.to_function()
    result = function(text='Philosopher Stone')
    assert result == 'UGhpbG9zb3BoZXIgU3RvbmU='


def test_decode():
    function = decode_base64.to_function()
    result = function(text='UGhpbG9zb3BoZXIgU3RvbmU=')
    assert result == 'Philosopher Stone'
