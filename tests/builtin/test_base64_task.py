from zrb.builtin.base64_task import base64_encode_task, base64_decode_task


def test_base64_encode():
    main_loop = base64_encode_task.create_main_loop()
    result = main_loop(text='Philosopher Stone')
    assert result == 'UGhpbG9zb3BoZXIgU3RvbmU='


def test_base64_decode():
    main_loop = base64_decode_task.create_main_loop()
    result = main_loop(text='UGhpbG9zb3BoZXIgU3RvbmU=')
    assert result == 'Philosopher Stone'
