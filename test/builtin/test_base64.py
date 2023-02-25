from zrb.builtin.base64 import encode, decode


def test_encode():
    main_loop = encode.create_main_loop()
    result = main_loop(text='Philosopher Stone')
    assert result == 'UGhpbG9zb3BoZXIgU3RvbmU='


def test_decode():
    main_loop = decode.create_main_loop()
    result = main_loop(text='UGhpbG9zb3BoZXIgU3RvbmU=')
    assert result == 'Philosopher Stone'
