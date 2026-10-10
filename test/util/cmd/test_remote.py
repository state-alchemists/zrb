import os
import shlex

from zrb.util.cmd.remote import get_remote_cmd_script


def test_script_uses_tty_by_default_and_t_upper_when_asked():
    assert get_remote_cmd_script("ls", host="h", user="u").startswith("ssh -t ")
    assert get_remote_cmd_script("ls", host="h", tty=False).startswith("ssh -T ")


def test_script_expands_a_leading_tilde_in_the_ssh_key():
    script = get_remote_cmd_script("ls", host="h", user="u", ssh_key="~/.ssh/id")
    assert f"-i {shlex.quote(os.path.expanduser('~/.ssh/id'))} " in script
    assert "'~" not in script


def test_script_omits_at_sign_without_user_and_uses_sshpass_for_password():
    script = get_remote_cmd_script("ls", host="h", use_password=True)
    assert script.startswith("sshpass -e ssh ") and " h " in script
