import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_class_code(original_code: str, class_name: str, new_code: str) -> str:
    """
    Replace the entire code body of a specified class.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        new_code (str): The new code body for the class as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
    return _modify_code(original_code, class_name, new_code, REPLACE)


def prepend_code_to_class(original_code: str, class_name: str, new_code: str) -> str:
    """
    Prepend code to the body of a specified class.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        new_code (str): The code to prepend as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
    return _modify_code(original_code, class_name, new_code, PREPEND)


def append_code_to_class(original_code: str, class_name: str, new_code: str) -> str:
    """
    Append code to the body of a specified class.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        new_code (str): The code to append as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
    return _modify_code(original_code, class_name, new_code, APPEND)


def _modify_code(original_code: str, class_name: str, new_code: str, mode: int) -> str:
    """
    Modify the code body of a specified class.

    Args:
        original_code (str): The original Python code as a string.
        class_name (str): The name of the class to modify.
        new_code (str): The code to add/replace as a string.
        mode (int): The modification mode (PREPEND, APPEND, or REPLACE).

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified class is not found in the code.
    """
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
    """
    A LibCST transformer to modify the code body of a ClassDef node.
    """

    def __init__(self, class_name: str, new_code: str, mode: int):
        """
        Initialize the transformer.

        Args:
            class_name (str): The name of the target class.
            new_code (str): The new code body as a string.
            mode (int): The modification mode (PREPEND, APPEND, or REPLACE).
        """
        self.class_name = class_name
        self.new_code = cst.parse_module(new_code).body
        self.class_found = False
        self.mode = mode

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """
        Called when leaving a ClassDef node. Modifies the body of the target class.
        """
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
