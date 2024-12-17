import libcst as cst


class ClassCodeAdder(cst.CSTTransformer):
    def __init__(self, class_name: str, new_code: str):
        self.class_name = class_name
        self.new_code = cst.parse_module(new_code).body
        self.class_found = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if this is the target class
        if original_node.name.value == self.class_name:
            self.class_found = True
            # Add the method to the class body
            new_body = updated_node.body.with_changes(
                body=updated_node.body.body + tuple(self.new_code)
            )
            return updated_node.with_changes(body=new_body)
        return updated_node


def append_code_to_class(original_code: str, class_name: str, new_code: str) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize transformer with the class name and method code
    transformer = ClassCodeAdder(class_name, new_code)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Check if the class was found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    # Return the modified code
    return modified_module.code
