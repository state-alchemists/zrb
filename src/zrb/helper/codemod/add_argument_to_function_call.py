import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
class AddArgumentTransformer(cst.CSTTransformer):
    def __init__(self, function_name: str, argument_name: str):
        self.function_name = function_name
        self.argument_name = argument_name
        super().__init__()

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if (
            isinstance(updated_node.func, cst.Name)
            and updated_node.func.value == self.function_name
        ):
            new_args = updated_node.args + (cst.Arg(cst.Name(self.argument_name)),)
            return updated_node.with_changes(args=new_args)
        return updated_node


@typechecked
def add_argument_to_function_call(
    code: str, function_name: str, argument_name: str
) -> str:
    module = cst.parse_module(code)
    transformed_module = module.visit(
        AddArgumentTransformer(function_name, argument_name)
    )
    return transformed_module.code
