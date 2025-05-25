from typing import Any, Dict

from zrb.builtin.group import jwt_group
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


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
    import json

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
        StrInput(name="secret", prompt="Secret", default=""),
        OptionInput(
            name="algorithm",
            prompt="Algorithm",
            default="HS256",
            options=["HS256", "HS384", "HS512"],
        ),
    ],
)
def decode_jwt(ctx: AnyContext) -> Dict[str, Any]:
    import jwt

    try:
        payload = jwt.decode(
            jwt=ctx.input.token, key=ctx.input.secret, algorithms=[ctx.input.algorithm]
        )
        ctx.print(payload)
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
