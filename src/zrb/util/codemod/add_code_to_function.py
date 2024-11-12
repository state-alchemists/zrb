import libcst as cst


class FunctionCodeAdder(cst.CSTTransformer):
    def __init__(self, function_name: str, new_code: str):
        self.function_name = function_name
        # Use parse_module to handle multiple statements
        self.new_code = cst.parse_statement(new_code)
        self.function_found = False

    def leave_FunctionDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if the class matches the target class
        if original_node.name.value == self.function_name:
            self.function_found = True
            # Add the method to the class body
            new_body = updated_node.body.with_changes(
                body=updated_node.body.body + (self.new_code,)
            )
            return updated_node.with_changes(body=new_body)
        return updated_node


def add_code_to_function(original_code: str, function_name: str, new_code: str) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = FunctionCodeAdder(function_name, new_code)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the class or function is not found
    if not transformer.function_found:
        raise ValueError(f"Function {function_name} not found.")
    # Return the modified code
    return modified_module.code
