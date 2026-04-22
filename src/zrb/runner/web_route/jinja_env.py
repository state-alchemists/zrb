from pathlib import Path

import jinja2

_TEMPLATES_DIR = Path(__file__).parent
_env: jinja2.Environment | None = None


def get_jinja_env() -> jinja2.Environment:
    global _env
    if _env is None:
        _env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=jinja2.select_autoescape(["html"]),
        )
    return _env
