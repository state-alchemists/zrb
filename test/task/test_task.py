from zrb import Env, StrInput, Task


def test_upstream_executed():
    lines = []
    create_naoh = Task(name="create-NaOH", action=lambda _: lines.append("NaOH"))
    create_hcl = Task(name="create-HCl", action=lambda _: lines.append("HCl"))
    create_nacl = Task(name="create-NaCl", action=lambda _: lines.append("NaCl"))
    create_nacl << [create_naoh, create_hcl]
    create_h2o = Task(name="create-H2O", action=lambda _: lines.append("H2O"))
    create_h2o << [create_naoh, create_hcl]
    create_nacl.run()
    assert len(lines) == 3
    assert "H2O" not in lines
    assert "NaOH" in lines
    assert "HCl" in lines
    assert "NaCl" == lines[-1]


def test_input_should_be_interpolated():
    lines = []
    ab = Task(
        name="ab",
        input=[StrInput("a"), StrInput("b")],
        action=lambda c: lines.append(
            f"{c.input.a} {c.input.b} {c.input.c} {c.input.d}"
        ),
    )
    bc = Task(
        name="bc",
        input=[StrInput("b"), StrInput("c")],
        action=lambda c: lines.append(
            f"{c.input.a} {c.input.b} {c.input.c} {c.input.d}"
        ),
    )
    d = Task(
        name="d",
        input=StrInput("d"),
        action=lambda c: lines.append(
            f"{c.input.a} {c.input.b} {c.input.c} {c.input.d}"
        ),
    )
    d << [ab, bc]
    d.run(str_kwargs={"a": "alpha", "b": "beta", "c": "gamma", "d": "delta"})
    assert len(lines) == 3
    assert lines[0] == "alpha beta gamma delta"
    assert lines[1] == "alpha beta gamma delta"
    assert lines[2] == "alpha beta gamma delta"


def test_env_should_be_isolated():
    lines = []
    hello = Task(
        name="hello",
        env=Env(name="NAME", default="world", link_to_os=False),
        action=lambda c: lines.append(f"hello {c.env.NAME}"),
    )
    hi = Task(
        name="hi",
        env=Env(name="NAME", default="sekai", link_to_os=False),
        action=lambda c: lines.append(f"hi {c.env.NAME}"),
    )
    greetings = Task(
        name="greetings",
        env=Env(name="NAME", default="universe", link_to_os=False),
        action=lambda c: lines.append(f"greetings {c.env.NAME}"),
    )
    hello >> hi >> greetings
    greetings.run()
    assert len(lines) == 3
    assert lines[0] == "hello world"
    assert lines[1] == "hi sekai"
    assert lines[2] == "greetings universe"
