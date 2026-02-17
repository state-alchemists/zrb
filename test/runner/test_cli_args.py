from zrb.runner.cli import Cli


def test_extract_kwargs_simple_flags():
    cli = Cli()
    kwargs, residual = cli._extract_kwargs_from_args(["--flag", "-s"])
    assert kwargs == {"flag": "true", "s": "true"}
    assert residual == []


def test_extract_kwargs_key_value_equals():
    cli = Cli()
    kwargs, residual = cli._extract_kwargs_from_args(["--key=val", "--num=1"])
    assert kwargs == {"key": "val", "num": "1"}
    assert residual == []


def test_extract_kwargs_key_value_space():
    cli = Cli()
    kwargs, residual = cli._extract_kwargs_from_args(["--key", "val", "--num", "1"])
    assert kwargs == {"key": "val", "num": "1"}
    assert residual == []


def test_extract_kwargs_mixed():
    cli = Cli()
    # command --flag pos1 --key val pos2 -s
    # Current behavior: --flag consumes pos1 as its value
    args = ["--flag", "pos1", "--key", "val", "pos2", "-s"]
    kwargs, residual = cli._extract_kwargs_from_args(args)
    assert kwargs == {"flag": "pos1", "key": "val", "s": "true"}
    assert residual == ["pos2"]


def test_extract_kwargs_flag_then_flag():
    cli = Cli()
    # --flag1 --flag2 val
    args = ["--flag1", "--flag2", "val"]
    kwargs, residual = cli._extract_kwargs_from_args(args)
    # flag1 is boolean true, flag2 takes "val"
    assert kwargs == {"flag1": "true", "flag2": "val"}
    assert residual == []


def test_extract_kwargs_flag_at_end():
    cli = Cli()
    args = ["val", "--flag"]
    kwargs, residual = cli._extract_kwargs_from_args(args)
    assert kwargs == {"flag": "true"}
    assert residual == ["val"]


def test_run_command_generation():
    cli = Cli()
    cmd = cli._get_run_command(["my", "task"], {"a": "1", "b": "hello world"})
    # Check parts because dict order might vary (though usually stable)
    assert "zrb my task" in cmd
    assert "--a 1" in cmd
    assert '--b "hello world"' in cmd
