import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_function_code(original_code: str, function_name: str, new_code: str) -> str:
    return _modify_function(original_code, function_name, new_code, REPLACE)


def prepend_code_to_function(
    original_code: str, function_name: str, new_code: str
) -> str:
    return _modify_function(original_code, function_name, new_code, PREPEND)


def append_code_to_function(
    original_code: str, function_name: str, new_code: str
) -> str:
    return _modify_function(original_code, function_name, new_code, APPEND)


def _modify_function(
    original_code: str, function_name: str, new_code: str, mode: int
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = _FunctionCodeModifier(function_name, new_code, mode)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the class or function is not found
    if not transformer.function_found:
        raise ValueError(f"Function {function_name} not found.")
    # Return the modified code
    return modified_module.code


class _FunctionCodeModifier(cst.CSTTransformer):
    def __init__(self, function_name: str, new_code: str, mode: int):
        self.function_name = function_name
        # Use parse_module to handle multiple statements
        self.new_code = cst.parse_module(new_code).body
        self.function_found = False
        self.mode = mode

    def leave_FunctionDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if the class matches the target class
        if original_node.name.value == self.function_name:
            self.function_found = True
            if self.mode == REPLACE:
                new_body = updated_node.body.with_changes(body=tuple(self.new_code))
                return updated_node.with_changes(body=new_body)
            if self.mode == PREPEND:
                new_body = updated_node.body.with_changes(
                    body=tuple(self.new_code) + updated_node.body.body
                )
                return updated_node.with_changes(body=new_body)
            if self.mode == APPEND:
                new_body = updated_node.body.with_changes(
                    body=updated_node.body.body + tuple(self.new_code)
                )
                return updated_node.with_changes(body=new_body)
        return updated_node
