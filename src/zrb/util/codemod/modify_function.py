import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_function_code(original_code: str, function_name: str, new_code: str) -> str:
    """
    Replace the entire code body of a specified function.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function to modify.
        new_code (str): The new code body for the function as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function is not found in the code.
    """
    return _modify_function(original_code, function_name, new_code, REPLACE)


def prepend_code_to_function(
    original_code: str, function_name: str, new_code: str
) -> str:
    """
    Prepend code to the body of a specified function.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function to modify.
        new_code (str): The code to prepend as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function is not found in the code.
    """
    return _modify_function(original_code, function_name, new_code, PREPEND)


def append_code_to_function(
    original_code: str, function_name: str, new_code: str
) -> str:
    """
    Append code to the body of a specified function.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function to modify.
        new_code (str): The code to append as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function is not found in the code.
    """
    return _modify_function(original_code, function_name, new_code, APPEND)


def _modify_function(
    original_code: str, function_name: str, new_code: str, mode: int
) -> str:
    """
    Modify the code body of a specified function.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function to modify.
        new_code (str): The code to add/replace as a string.
        mode (int): The modification mode (PREPEND, APPEND, or REPLACE).

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function is not found in the code.
    """
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
    """
    A LibCST transformer to modify the code body of a FunctionDef node.
    """

    def __init__(self, function_name: str, new_code: str, mode: int):
        """
        Initialize the transformer.

        Args:
            function_name (str): The name of the target function.
            new_code (str): The new code body as a string.
            mode (int): The modification mode (PREPEND, APPEND, or REPLACE).
        """
        self.function_name = function_name
        # Use parse_module to handle multiple statements
        self.new_code = cst.parse_module(new_code).body
        self.function_found = False
        self.mode = mode

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """
        Called when leaving a FunctionDef node. Modifies the body of the target function.
        """
        # Check if the function matches the target function
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
