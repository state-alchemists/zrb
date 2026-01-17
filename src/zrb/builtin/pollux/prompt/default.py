import os


def get_default_prompt(name: str) -> str:
    cwd = os.path.dirname(__file__)
    with open(os.path.join(cwd, f"{name}.md")) as f:
        return f.read()
