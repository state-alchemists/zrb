"""Redaction for values that must not reach a log.

`CmdTask` logs its whole environment map at DEBUG level, and DEBUG is exactly
what a maintainer asks a user to turn on before pasting output into a bug
report — so every API key, token and password in that user's shell went with
it. Matching on the *name* is the only option available there: the values are
arbitrary process environment, not zrb's own `EnvField`s (which carry an
explicit `secret` flag and are handled by `zrb config explain`).

Name-matching is a heuristic, so it is tuned to over-redact rather than
under-redact, and `CFG.SECRET_ENV_PATTERNS` lets a project widen or narrow it.
"""

from collections.abc import Mapping

SECRET_MASK = "***"


def is_secret_env_name(name: str, patterns: "list[str]") -> bool:
    """Whether `name` looks like it holds a credential.

    Case-insensitive substring match, so `AWS_SECRET_ACCESS_KEY`,
    `openai_api_key` and `MY_DB_PASSWORD` all match on their respective
    patterns.
    """
    upper = name.upper()
    return any(pattern and pattern.upper() in upper for pattern in patterns)


def redact_env_map(
    env_map: "Mapping[str, str]", patterns: "list[str]"
) -> "dict[str, str]":
    """A copy of `env_map` with credential-looking values replaced by the mask.

    Names are kept: knowing that `OPENAI_API_KEY` was set is the useful half of
    the debug output, and the value is the half that must not be.
    """
    return {
        name: SECRET_MASK if is_secret_env_name(name, patterns) else value
        for name, value in env_map.items()
    }
