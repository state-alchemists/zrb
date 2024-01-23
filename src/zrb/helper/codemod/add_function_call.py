import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
def add_function_call(code: str, function_name: str, parameters: list) -> str:
    """
    Adds a function call statement to the end of a module with the specified
    function name and parameters.

    Args:
        code (str): The code of the module to modify.
        function_name (str): The name of the function to call.
        parameters (list): A list of parameters to pass to the function call.

    Returns:
        str: The modified code with the new function call statement added.
    """

    module = cst.parse_module(code)

    # Create the new function call statement
    new_function_call = cst.Expr(
        value=cst.Call(
            func=cst.Name(value=function_name),
            args=[cst.Arg(value=cst.parse_expression(param)) for param in parameters],
        )
    )

    module.body.append(cst.SimpleStatementLine([new_function_call]))

    # Generate the modified code
    modified_code = module.code
    return modified_code
