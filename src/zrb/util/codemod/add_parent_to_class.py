import libcst as cst


class ParentClassAdder(cst.CSTTransformer):
    def __init__(self, class_name: str, parent_class_name: str):
        self.class_name = class_name
        self.parent_class_name = parent_class_name
        self.class_found = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if this is the target class
        if original_node.name.value == self.class_name:
            self.class_found = True
            # Add the parent class to the existing bases
            new_bases = (
                cst.Arg(value=cst.Name(self.parent_class_name)),
                *updated_node.bases,
            )
            return updated_node.with_changes(bases=new_bases)
        return updated_node


def add_parent_to_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize transformer with the class name and parent class name
    transformer = ParentClassAdder(class_name, parent_class_name)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Check if the class was found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    # Return the modified code
    return modified_module.code
