from zrb.builtin.group import ulid_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="generate-ulid",
    description="🔨 Generate ULID",
    group=ulid_group,
    alias="generate",
)
def generate_ulid(ctx: AnyContext) -> str:

    # lazy: heavy third-party
    import ulid

    result = ulid.new().str
    ctx.print(result)
    return result


ulid_group.add_task(generate_ulid, alias="generate")


@make_task(
    name="validate-ulid",
    description="✅ Validate ULID",
    input=StrInput(name="id"),
    group=ulid_group,
    alias="validate",
)
def validate_ulid(ctx: AnyContext) -> bool:

    # lazy: heavy third-party
    import ulid

    try:
        ulid.parse(ctx.input.id)
        ctx.print("Valid ULID")
        return True
    except Exception:
        ctx.print("Invalid ULID")
        return False
