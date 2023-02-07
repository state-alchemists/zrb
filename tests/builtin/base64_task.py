from zrb.builtin.base64_task import base64_encode, base64_decode


def test_base64_encode():
    main_loop = base64_encode.create_main_loop()
    result = main_loop(text='md5_test_sum.txt')
    assert result == 'UGhpbG9zb3BoZXIgU3RvbmU='


def test_base64_decode():
    main_loop = base64_decode.create_main_loop()
    result = main_loop(text='UGhpbG9zb3BoZXIgU3RvbmU=')
    assert result == 'Philosopher Stone'
