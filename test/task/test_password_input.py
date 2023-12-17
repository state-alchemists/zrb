from zrb.task_input.password_input import PasswordInput


def test_password_input():
    password_input = PasswordInput(name='password_input')
    assert password_input.is_hidden()
