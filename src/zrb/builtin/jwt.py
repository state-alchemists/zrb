import datetime
import json
from typing import Any

from zrb.builtin.group import jwt_group
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task

_TIMESTAMP_CLAIMS = ("exp", "iat", "nbf", "auth_time")


def _humanize_claims(ctx: AnyContext, payload: dict[str, Any]) -> None:
    """Print human-readable values for well-known timestamp claims (stderr)."""
    for claim in _TIMESTAMP_CLAIMS:
        value = payload.get(claim)
        if isinstance(value, (int, float)):
            human = datetime.datetime.fromtimestamp(
                value, tz=datetime.timezone.utc
            ).isoformat()
            ctx.print(f"  {claim}: {value} ({human})")


@make_task(
    name="encode-jwt",
    description="🔒 Encode JWT token",
    group=jwt_group,
    alias="encode",
    input=[
        StrInput(name="secret", prompt="Secret", default=""),
        StrInput(name="payload", prompt="Payload (JSON format)", default="{}"),
        OptionInput(
            name="algorithm",
            prompt="Algorithm",
            default="HS256",
            options=["HS256", "HS384", "HS512"],
        ),
    ],
)
def encode_jwt(ctx: AnyContext) -> str:

    # lazy: heavy third-party
    import jwt

    try:
        payload = json.loads(ctx.input.payload)
        token = jwt.encode(
            payload=payload, key=ctx.input.secret, algorithm=ctx.input.algorithm
        )
        ctx.print(token)
        return token
    except Exception as e:
        ctx.print_err(f"Failed to encode JWT: {e}")
        raise


@make_task(
    name="decode-jwt",
    description="🔓 Decode JWT token",
    group=jwt_group,
    alias="decode",
    input=[
        StrInput(name="token", prompt="Token", default=""),
        BoolInput(
            name="verify",
            description="Verify the signature (requires the correct secret)",
            default=False,
            always_prompt=False,
        ),
        StrInput(
            name="secret",
            prompt="Secret (only used when verifying)",
            default="",
            always_prompt=False,
        ),
        OptionInput(
            name="algorithm",
            prompt="Algorithm",
            default="HS256",
            options=["HS256", "HS384", "HS512"],
            always_prompt=False,
        ),
    ],
)
def decode_jwt(ctx: AnyContext) -> dict[str, Any]:
    # lazy: heavy third-party
    import jwt

    try:
        # Default is inspect-without-verify (the jwt.io use case): paste a token
        # and read its claims with no secret. Pass --verify to check the signature.
        payload = jwt.decode(
            jwt=ctx.input.token,
            key=ctx.input.secret,
            algorithms=[ctx.input.algorithm],
            options={"verify_signature": ctx.input.verify},
        )
        ctx.print(payload)
        _humanize_claims(ctx, payload)
        return payload
    except Exception as e:
        ctx.print_err(f"Failed to decode JWT: {e}")
        raise


@make_task(
    name="validate-jwt",
    description="✅ Validate JWT token",
    group=jwt_group,
    alias="validate",
    input=[
        StrInput(name="token", prompt="Token", default=""),
        StrInput(name="secret", prompt="Secret", default=""),
        OptionInput(
            name="algorithm",
            prompt="Algorithm",
            default="HS256",
            options=["HS256", "HS384", "HS512"],
        ),
    ],
)
def validate_jwt(ctx: AnyContext) -> bool:
    # lazy: heavy third-party
    import jwt

    try:
        jwt.decode(
            jwt=ctx.input.token, key=ctx.input.secret, algorithms=[ctx.input.algorithm]
        )
        ctx.print("✅ Token is valid")
        return True
    except jwt.ExpiredSignatureError:
        ctx.print_err("❌ Token has expired")
        return False
    except jwt.InvalidTokenError:
        ctx.print_err("❌ Invalid token")
        return False
    except Exception as e:
        ctx.print_err(f"❌ Validation failed: {e}")
        return False
