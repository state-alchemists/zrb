from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import CoreSchema


class PydanticInstanceSchemaMixin:
    """Lets an ABC sit inside a pydantic-validated signature as an opaque,
    instance-checked value.

    `pydantic_ai` inspects tool-function signatures (e.g. `ctx: AnyContext`)
    to build their schema; without this, pydantic has no way to validate an
    arbitrary ABC like `AnyContext`/`AnySharedContext`/`AnySession` and raises.
    `core_schema.is_instance_schema` tells it "accept any instance of this
    class, don't try to validate its fields," and the JSON schema exposes it
    as an opaque object titled after the class doing the embedding.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: "GetCoreSchemaHandler"
    ) -> "CoreSchema":
        # lazy: heavy third-party
        from pydantic_core import core_schema

        return core_schema.is_instance_schema(cls)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: "CoreSchema", handler: "GetJsonSchemaHandler"
    ) -> "JsonSchemaValue":
        return {"type": "object", "title": cls.__name__}
