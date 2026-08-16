from zrb.util.pydantic_schema import PydanticInstanceSchemaMixin


class _Widget(PydanticInstanceSchemaMixin):
    pass


class _Gadget(PydanticInstanceSchemaMixin):
    pass


def test_core_schema_accepts_any_instance_of_the_class():
    from pydantic_core import core_schema

    schema = _Widget.__get_pydantic_core_schema__(_Widget, None)
    assert schema["type"] == "is-instance"
    assert schema["cls"] is _Widget
    assert schema == core_schema.is_instance_schema(_Widget)


def test_json_schema_titles_itself_after_the_class_name():
    schema = _Widget.__get_pydantic_core_schema__(_Widget, None)
    json_schema = _Widget.__get_pydantic_json_schema__(schema, None)
    assert json_schema == {"type": "object", "title": "_Widget"}


def test_json_schema_title_varies_per_class_reusing_the_same_mixin():
    widget_schema = _Widget.__get_pydantic_core_schema__(_Widget, None)
    gadget_schema = _Gadget.__get_pydantic_core_schema__(_Gadget, None)

    widget_json_schema = _Widget.__get_pydantic_json_schema__(widget_schema, None)
    gadget_json_schema = _Gadget.__get_pydantic_json_schema__(gadget_schema, None)

    assert widget_json_schema["title"] == "_Widget"
    assert gadget_json_schema["title"] == "_Gadget"
