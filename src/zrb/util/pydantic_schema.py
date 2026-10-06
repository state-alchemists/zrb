from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import CoreSchema


class PydanticInstanceSchemaMixin:
    """Lets an ABC sit inside a pydantic-validated signature as an opaque,
    instance-checked value.

    `pydantic_ai` builds schemas from tool signatures (`ctx: AnyContext`),
    and pydantic cannot otherwise validate an arbitrary ABC.
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
