import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
class AppendCodeTransformer(cst.CSTTransformer):
    def __init__(self, function_name: str, new_code: str):
        self.function_name = function_name
        self.new_code = new_code
        super().__init__()

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if updated_node.name.value == self.function_name:
            new_body = updated_node.body.body + (cst.parse_statement(self.new_code),)
            return updated_node.with_changes(body=cst.IndentedBlock(body=new_body))
        return updated_node


@typechecked
def append_code_to_function(code: str, function_name: str, new_code: str) -> str:
    module = cst.parse_module(code)
    transformed_module = module.visit(AppendCodeTransformer(function_name, new_code))
    return transformed_module.code
