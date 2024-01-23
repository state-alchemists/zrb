import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
class AddKeyValuePairTransformer(cst.CSTTransformer):
    def __init__(
        self,
        dict_name: str,
        key_node: cst.BaseExpression,
        value_node: cst.BaseExpression,
    ):
        self.dict_name = dict_name
        self.key_node = key_node
        self.value_node = value_node
        super().__init__()

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign:
        if (
            isinstance(updated_node.value, cst.Dict)
            and isinstance(updated_node.targets[0].target, cst.Name)
            and updated_node.targets[0].target.value == self.dict_name
        ):
            for element in updated_node.value.elements:
                key = element.key
                if isinstance(key, cst.BaseExpression) and key.value == self.key_node:
                    return updated_node
            new_elements = updated_node.value.elements + (
                cst.DictElement(self.key_node, self.value_node),
            )
            new_value = cst.Dict(new_elements)
            return updated_node.with_changes(value=new_value)
        return updated_node


def add_key_value_to_dict(code: str, dict_name: str, key: str, value: str) -> str:
    module = cst.parse_module(code)
    key_node = cst.parse_expression(key)
    value_node = cst.parse_expression(value)
    transformed_module = module.visit(
        AddKeyValuePairTransformer(dict_name, key_node, value_node)
    )
    return transformed_module.code
