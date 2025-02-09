import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_parent_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    return _modify_parent_class(original_code, class_name, parent_class_name, REPLACE)


def append_parent_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    return _modify_parent_class(original_code, class_name, parent_class_name, APPEND)


def prepend_parent_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    return _modify_parent_class(original_code, class_name, parent_class_name, PREPEND)


def _modify_parent_class(
    original_code: str, class_name: str, parent_class_name: str, mode: int
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize transformer with the class name and parent class name
    transformer = _ParentClassAdder(class_name, parent_class_name, mode)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Check if the class was found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    # Return the modified code
    return modified_module.code


class _ParentClassAdder(cst.CSTTransformer):
    def __init__(self, class_name: str, parent_class_name: str, mode: int):
        self.class_name = class_name
        self.parent_class_name = parent_class_name
        self.class_found = False
        self.mode = mode

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if this is the target class
        if original_node.name.value == self.class_name:
            self.class_found = True
            if self.mode == REPLACE:
                new_bases = (cst.Arg(value=cst.Name(self.parent_class_name)),)
                return updated_node.with_changes(bases=new_bases)
            if self.mode == PREPEND:
                new_bases = (
                    cst.Arg(value=cst.Name(self.parent_class_name)),
                    *updated_node.bases,
                )
                return updated_node.with_changes(bases=new_bases)
            if self.mode == APPEND:
                new_bases = (
                    *updated_node.bases,
                    cst.Arg(value=cst.Name(self.parent_class_name)),
                )
                return updated_node.with_changes(bases=new_bases)
        return updated_node
