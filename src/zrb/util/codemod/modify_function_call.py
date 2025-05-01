import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND, REPLACE


def replace_function_call_param(
    original_code: str, function_name: str, new_param: str
) -> str:
    """
    Replace the parameters of a specified function call.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function call to modify.
        new_param (str): The new parameter(s) as a string (e.g., "param1, param2=value").

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function call is not found in the code.
    """
    return _modify_function_call(original_code, function_name, new_param, REPLACE)


def prepend_param_to_function_call(
    original_code: str, function_name: str, new_param: str
) -> str:
    """
    Prepend a parameter to a specified function call.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function call to modify.
        new_param (str): The parameter to prepend as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function call is not found in the code.
    """
    return _modify_function_call(original_code, function_name, new_param, PREPEND)


def append_param_to_function_call(
    original_code: str, function_name: str, new_param: str
) -> str:
    """
    Append a parameter to a specified function call.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function call to modify.
        new_param (str): The parameter to append as a string.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function call is not found in the code.
    """
    return _modify_function_call(original_code, function_name, new_param, APPEND)


def _modify_function_call(
    original_code: str, function_name: str, new_param: str, mode: int
) -> str:
    """
    Modify the parameters of a specified function call.

    Args:
        original_code (str): The original Python code as a string.
        function_name (str): The name of the function call to modify.
        new_param (str): The parameter(s) to add/replace as a string.
        mode (int): The modification mode (PREPEND, APPEND, or REPLACE).

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified function call is not found in the code.
    """
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = _FunctionCallParamModifier(function_name, new_param, mode)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the function call is not found
    if not transformer.param_added:
        raise ValueError(
            f"Function call to {function_name} not found in the provided code."
        )
    # Return the modified code
    return modified_module.code


class _FunctionCallParamModifier(cst.CSTTransformer):
    """
    A LibCST transformer to modify the parameters of a function call.
    """

    def __init__(self, func_name: str, new_param: str, mode: int):
        """
        Initialize the transformer.

        Args:
            func_name (str): The name of the target function.
            new_param (str): The new parameter(s) as a string.
            mode (int): The modification mode (PREPEND, APPEND, or REPLACE).
        """
        self.func_name = func_name
        # Parse the new parameter to ensure it’s a valid CST node
        self.new_param = cst.parse_expression(new_param)
        self.param_added = False
        self.mode = mode

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """
        Called when leaving a Call node. Modifies the arguments of the target function call.
        """
        # Check if the function call name matches the target function
        if (
            isinstance(original_node.func, cst.Name)
            and original_node.func.value == self.func_name
        ):
            if self.mode == REPLACE:
                new_args = (cst.Arg(value=self.new_param),)
                self.param_added = True
                return updated_node.with_changes(args=new_args)
            if self.mode == PREPEND:
                new_args = (cst.Arg(value=self.new_param),) + updated_node.args
                self.param_added = True
                return updated_node.with_changes(args=new_args)
            if self.mode == APPEND:
                new_args = updated_node.args + (cst.Arg(value=self.new_param),)
                self.param_added = True
                return updated_node.with_changes(args=new_args)
        return updated_node
