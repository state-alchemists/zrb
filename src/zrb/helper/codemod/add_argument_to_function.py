import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
class AddArgumentTransformer(cst.CSTTransformer):
    def __init__(self, function_name: str, argument_name: str, argument_type: str):
        self.function_name = function_name
        self.argument_name = argument_name
        self.argument_type = argument_type
        super().__init__()

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if updated_node.name.value == self.function_name:
            new_params = updated_node.params.params + (
                cst.Param(
                    cst.Name(self.argument_name),
                    cst.Annotation(cst.Name(self.argument_type)),
                ),
            )
            return updated_node.with_changes(
                params=cst.Parameters(new_params),
            )
        return updated_node


@typechecked
def add_argument_to_function(
    code: str, function_name: str, argument_name: str, argument_type: str
) -> str:
    module = cst.parse_module(code)
    transformed_module = module.visit(
        AddArgumentTransformer(function_name, argument_name, argument_type)
    )
    return transformed_module.code
