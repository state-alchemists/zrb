from zrb.util.cmd.remote import bracket_ipv6, get_remote_cmd_script


def test_script_uses_tty_by_default_and_t_upper_when_asked():
    assert get_remote_cmd_script("ls", host="h", user="u").startswith("ssh -t ")
    assert get_remote_cmd_script("ls", host="h", tty=False).startswith("ssh -T ")


def test_script_omits_at_sign_without_user_and_uses_sshpass_for_password():
    script = get_remote_cmd_script("ls", host="h", use_password=True)
    assert script.startswith("sshpass -e ssh ") and " h " in script


def test_bracket_ipv6_wraps_only_unbracketed_literals():
    assert bracket_ipv6("2001:db8::1") == "[2001:db8::1]"
    assert bracket_ipv6("[2001:db8::1]") == "[2001:db8::1]"
    assert bracket_ipv6("example.com") == "example.com"
    assert bracket_ipv6("10.0.0.1") == "10.0.0.1"
