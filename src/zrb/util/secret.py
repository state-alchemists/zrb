"""Name-based redaction for values that must not reach a log.

The heuristic over-redacts; `CFG.SECRET_ENV_PATTERNS` tunes it. zrb's own
knobs use `EnvField(secret=True)` instead.
"""

from collections.abc import Mapping

SECRET_MASK = "***"


def is_secret_env_name(name: str, patterns: "list[str]") -> bool:
    """Whether `name` looks like it holds a credential.

    Case-insensitive substring match; an empty pattern matches nothing.
    """
    upper = name.upper()
    return any(pattern and pattern.upper() in upper for pattern in patterns)


def redact_env_map(
    env_map: "Mapping[str, str]", patterns: "list[str]"
) -> "dict[str, str]":
    """A copy of `env_map` with credential-looking values replaced by the mask."""
    return {
        name: SECRET_MASK if is_secret_env_name(name, patterns) else value
        for name, value in env_map.items()
    }
