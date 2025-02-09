import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_class_code(original_code: str, class_name: str, new_code: str) -> str:
    return _modify_code(original_code, class_name, new_code, REPLACE)


def prepend_code_to_class(original_code: str, class_name: str, new_code: str) -> str:
    return _modify_code(original_code, class_name, new_code, PREPEND)


def append_code_to_class(original_code: str, class_name: str, new_code: str) -> str:
    return _modify_code(original_code, class_name, new_code, APPEND)


def _modify_code(original_code: str, class_name: str, new_code: str, mode: int) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize transformer with the class name and method code
    transformer = _ClassCodeModifier(class_name, new_code, mode)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Check if the class was found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    # Return the modified code
    return modified_module.code


class _ClassCodeModifier(cst.CSTTransformer):
    def __init__(self, class_name: str, new_code: str, mode: int):
        self.class_name = class_name
        self.new_code = cst.parse_module(new_code).body
        self.class_found = False
        self.mode = mode

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if this is the target class
        if original_node.name.value == self.class_name:
            self.class_found = True
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
