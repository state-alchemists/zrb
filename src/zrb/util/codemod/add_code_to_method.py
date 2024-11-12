import libcst as cst


class MethodCodeAdder(cst.CSTTransformer):
    def __init__(self, class_name: str, method_name: str, new_code: str):
        self.class_name = class_name
        self.method_name = method_name
        # Use parse_module to handle multiple statements
        self.new_code = cst.parse_statement(new_code)
        self.class_found = False
        self.method_found = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if the class matches the target class
        if original_node.name.value == self.class_name:
            self.class_found = True
            # Now, modify function definitions inside this class
            new_body = []
            for (
                item
            ) in updated_node.body.body:  # Access body.body, not just updated_node.body
                if (
                    isinstance(item, cst.FunctionDef)
                    and item.name.value == self.method_name
                ):
                    # Modify the target function by adding the new code
                    body_with_new_code = item.body.with_changes(
                        body=item.body.body + (self.new_code,)  # Add the new code
                    )
                    new_body.append(item.with_changes(body=body_with_new_code))
                    self.method_found = True
                else:
                    new_body.append(item)
            return updated_node.with_changes(body=cst.IndentedBlock(new_body))
        return updated_node


def add_code_to_method(
    original_code: str, class_name: str, function_name: str, new_code: str
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = MethodCodeAdder(class_name, function_name, new_code)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the class or function is not found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    if not transformer.method_found:
        raise ValueError(f"Method {function_name} not found in class {class_name}.")
    # Return the modified code
    return modified_module.code
