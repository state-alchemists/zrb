import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_parent_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    """
    Replace the parent class of a specified class in the provided code.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        parent_class_name (str): The new parent class name.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
    return _modify_parent_class(original_code, class_name, parent_class_name, REPLACE)


def append_parent_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    """
    Append a parent class to a specified class in the provided code.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        parent_class_name (str): The parent class name to append.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
    return _modify_parent_class(original_code, class_name, parent_class_name, APPEND)


def prepend_parent_class(
    original_code: str, class_name: str, parent_class_name: str
) -> str:
    """
    Prepend a parent class to a specified class in the provided code.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        parent_class_name (str): The parent class name to prepend.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
    return _modify_parent_class(original_code, class_name, parent_class_name, PREPEND)


def _modify_parent_class(
    original_code: str, class_name: str, parent_class_name: str, mode: int
) -> str:
    """
    Modify the parent class(es) of a specified class in the provided code.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        parent_class_name (str): The parent class name to add/replace.
        mode (int): The modification mode (PREPEND, APPEND, or REPLACE).

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
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
        """
        Initialize the transformer.

        Args:
            class_name (str): The name of the target class.
            parent_class_name (str): The name of the parent class to add/replace.
            mode (int): The modification mode (PREPEND, APPEND, or REPLACE).
        """
        self.class_name = class_name
        self.parent_class_name = parent_class_name
        self.class_found = False
        self.mode = mode

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """
        Called when leaving a ClassDef node. Modifies the bases of the target class.
        """
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
