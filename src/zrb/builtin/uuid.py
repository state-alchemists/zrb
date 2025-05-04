from zrb.builtin.group import (
    uuid_group,
    uuid_v1_group,
    uuid_v3_group,
    uuid_v4_group,
    uuid_v5_group,
)
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="generate-uuid-v1",
    description="🔨 Generate UUID V1",
    input=[
        StrInput(
            name="node",
            description="48-bit hardware address as integer (leave empty for random)",
            prompt="Enter node address (48-bit integer)",
            allow_empty=True,
        ),
        StrInput(
            name="clock-seq",
            description="14-bit sequence number as integer (leave empty for random)",
            prompt="Enter clock sequence (14-bit integer)",
            allow_empty=True,
        ),
    ],
    group=uuid_v1_group,
    alias="generate",
)
def generate_uuid_v1(ctx: AnyContext) -> str:
    import uuid

    result = str(
        uuid.uuid1(
            node=int(ctx.input.node) if ctx.input.node != "" else None,
            clock_seq=int(ctx.input.clock_seq) if ctx.input.clock_seq != "" else None,
        )
    )
    ctx.print(result)
    return result


@make_task(
    name="generate-uuid-v3",
    description="🔨 Generate UUID v3 (MD5 namespace-based)",
    input=[
        OptionInput(
            name="namespace",
            description="Namespace for v3",
            prompt="Select a namespace",
            options=["dns", "url", "oid", "x500"],
        ),
        StrInput(
            name="name",
            description="Name string",
            prompt="Enter the name to namespace-hash",
        ),
    ],
    group=uuid_v3_group,
    alias="generate",
)
def generate_uuid_v3(ctx: AnyContext) -> str:
    import uuid

    ns_map = {
        "dns": uuid.NAMESPACE_DNS,
        "url": uuid.NAMESPACE_URL,
        "oid": uuid.NAMESPACE_OID,
        "x500": uuid.NAMESPACE_X500,
    }
    namespace = ns_map[ctx.input.namespace]
    result = str(uuid.uuid3(namespace, ctx.input.name))
    ctx.print(result)
    return result


@make_task(
    name="generate-uuid-v4",
    description="🔨 Generate UUID v4 (random)",
    group=uuid_v4_group,
    alias="generate",
)
def generate_uuid_v4(ctx: AnyContext) -> str:
    import uuid

    result = str(uuid.uuid4())
    ctx.print(result)
    return result


uuid_group.add_task(generate_uuid_v4, alias="generate")


@make_task(
    name="generate-uuid-v5",
    description="🔨 Generate UUID v5 (SHA1 namespace-based)",
    input=[
        OptionInput(
            name="namespace",
            description="Namespace for v5",
            prompt="Select a namespace",
            options=["dns", "url", "oid", "x500"],
        ),
        StrInput(
            name="name",
            description="Name string",
            prompt="Enter the name to namespace-hash",
        ),
    ],
    group=uuid_v5_group,
    alias="generate",
)
def generate_uuid_v5(ctx: AnyContext) -> str:
    import uuid

    ns_map = {
        "dns": uuid.NAMESPACE_DNS,
        "url": uuid.NAMESPACE_URL,
        "oid": uuid.NAMESPACE_OID,
        "x500": uuid.NAMESPACE_X500,
    }
    namespace = ns_map[ctx.input.namespace]
    result = str(uuid.uuid5(namespace, ctx.input.name))
    ctx.print(result)
    return result


@make_task(
    name="validate-uuid",
    description="✅ Validate UUID",
    input=StrInput(name="id"),
    group=uuid_group,
    alias="validate",
)
def validate_uuid(ctx: AnyContext) -> bool:
    import uuid

    try:
        uuid.UUID(ctx.input.id, version=1)
        ctx.print("Valid UUID")
        return True
    except Exception:
        ctx.print("Invalid UUID")
        return False


@make_task(
    name="validate-uuid-v1",
    description="✅ Validate UUID V1",
    input=StrInput(name="id"),
    group=uuid_v1_group,
    alias="validate",
)
def validate_uuid_v1(ctx: AnyContext) -> bool:
    import uuid

    try:
        uuid.UUID(ctx.input.id, version=1)
        ctx.print("Valid UUID V1")
        return True
    except Exception:
        ctx.print("Invalid UUID V1")
        return False


@make_task(
    name="validate-uuid-v3",
    description="✅ Validate UUID V3",
    input=StrInput(name="id"),
    group=uuid_v3_group,
    alias="validate",
)
def validate_uuid_v3(ctx: AnyContext) -> bool:
    import uuid

    try:
        uuid.UUID(ctx.input.id, version=3)
        ctx.print("Valid UUID V3")
        return True
    except Exception:
        ctx.print("Invalid UUID V3")
        return False


@make_task(
    name="validate-uuid-v4",
    description="✅ Validate UUID V4",
    input=StrInput(name="id"),
    group=uuid_v4_group,
    alias="validate",
)
def validate_uuid_v4(ctx: AnyContext) -> bool:
    import uuid

    try:
        uuid.UUID(ctx.input.id, version=4)
        ctx.print("Valid UUID V4")
        return True
    except Exception:
        ctx.print("Invalid UUID V4")
        return False


@make_task(
    name="validate-uuid-v5",
    description="✅ Validate UUID V5",
    input=StrInput(name="id"),
    group=uuid_v5_group,
    alias="validate",
)
def validate_uuid_v5(ctx: AnyContext) -> bool:
    import uuid

    try:
        uuid.UUID(ctx.input.id, version=5)
        ctx.print("Valid UUID V5")
        return True
    except Exception:
        ctx.print("Invalid UUID V5")
        return False
