"""Name-based redaction for values that must not reach a log.

Matching on the name is the only option for arbitrary process environment: the
values carry no metadata. zrb's own knobs are separate — they declare
`EnvField(secret=True)` and are masked by `zrb config explain`.

The match is a heuristic, tuned to over-redact: a false positive costs one
unhelpful `***` in a debug log, a false negative leaks a credential.
`CFG.SECRET_ENV_PATTERNS` widens or narrows it.
"""

from collections.abc import Mapping

SECRET_MASK = "***"


def is_secret_env_name(name: str, patterns: "list[str]") -> bool:
    """Whether `name` looks like it holds a credential.

    Case-insensitive substring match, so `AWS_SECRET_ACCESS_KEY`,
    `openai_api_key` and `MY_DB_PASSWORD` each match on a different pattern.
    An empty pattern matches nothing rather than everything, so a trailing
    comma in the env var cannot mask the whole map.
    """
    upper = name.upper()
    return any(pattern and pattern.upper() in upper for pattern in patterns)


def redact_env_map(
    env_map: "Mapping[str, str]", patterns: "list[str]"
) -> "dict[str, str]":
    """A copy of `env_map` with credential-looking values replaced by the mask.

    Names survive: that `OPENAI_API_KEY` is set is the half of a debug dump
    worth reading, and the value is the half that must not travel.
    """
    return {
        name: SECRET_MASK if is_secret_env_name(name, patterns) else value
        for name, value in env_map.items()
    }
