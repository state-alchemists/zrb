"""Whether this host may be bound at all: the check `server start` fails closed on.

A non-loopback bind that is not actually secured is refused before the app is
built, for either of two distinct risks: auth off (unauthenticated exposure), or
auth on with credentials anyone who read the docs already has. There is
deliberately no override flag — ADR-0087 records why.

`start_server` in `runner/cli.py` is the only caller; this module is where the
policy lives so that "where do we refuse an insecure bind" has an answer other
than a CLI file.
"""

import ipaddress
import sys

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.util.cli.style import stylize_error

# Literal IP addresses are parsed instead of listed.
_LOOPBACK_HOSTNAMES = {"localhost"}

# Credential minimums, enforced only for a network-exposed bind.
_MIN_PUBLIC_PASSWORD_LENGTH = 12
_MIN_PUBLIC_SECRET_KEY_LENGTH = 32


def is_loopback_bind(host: str) -> bool:
    """True when `host` provably binds to loopback only; unknown names count as exposed."""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() in _LOOPBACK_HOSTNAMES


def refuse_insecure_bind(host: str, auth_config: WebAuthConfig) -> None:
    """Exit unless a non-loopback bind has auth enabled with usable credentials.

    There is no override flag. Checks the effective `auth_config`, not CFG,
    since callers may override it programmatically (including with "").
    """
    if is_loopback_bind(host):
        return
    if not auth_config.enable_auth:
        _abort_insecure_bind(
            f"Refusing to bind to '{host}' without authentication "
            "(WEB_AUTH_ENABLED=off): this exposes task execution to anyone "
            "who can reach this host.\n"
            "  Fix: set WEB_AUTH_ENABLED=on together with a real "
            "WEB_SUPER_ADMIN_PASSWORD and WEB_SECRET_KEY,\n"
            "       or bind to 127.0.0.1 (the default)."
        )
    problems = _credential_problems(auth_config)
    if problems:
        listed = "\n".join(f"  - {problem}" for problem in problems)
        _abort_insecure_bind(
            f"Refusing to bind to '{host}': authentication is enabled, but "
            f"the credentials protecting it are not usable.\n{listed}\n"
            "  Fix: set each to a unique value of the stated length, or bind "
            "to 127.0.0.1 (the default)."
        )


def _credential_problems(auth_config: WebAuthConfig) -> list[str]:
    """Every reason the effective credentials cannot protect a public bind."""
    return [
        problem
        for problem in (
            _credential_problem(
                "WEB_SUPER_ADMIN_PASSWORD",
                auth_config.super_admin_password,
                CFG.DEFAULT_WEB_SUPER_ADMIN_PASSWORD,
                _MIN_PUBLIC_PASSWORD_LENGTH,
            ),
            _credential_problem(
                "WEB_SECRET_KEY",
                auth_config.secret_key,
                CFG.DEFAULT_WEB_SECRET_KEY,
                _MIN_PUBLIC_SECRET_KEY_LENGTH,
            ),
        )
        if problem is not None
    ]


def _credential_problem(
    name: str, value: str, shipped_default: str, min_length: int
) -> str | None:
    """Why `value` is unfit to protect a public bind, or None when it is fit."""
    if value.strip() == "":
        return f"{name} is empty."
    if value == shipped_default:
        return (
            f"{name} still has its default, publicly-documented value -- "
            "anyone who read zrb's docs has it."
        )
    if len(value) < min_length:
        return f"{name} is shorter than the {min_length}-character minimum."
    return None


def _abort_insecure_bind(message: str) -> None:
    """Print a refusal and exit non-zero, so CI and shells see the failure."""
    print(stylize_error(f"\n{message}"), file=sys.stderr)
    raise SystemExit(1)
