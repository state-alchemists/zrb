import libcst as cst


class FunctionCallParamAdder(cst.CSTTransformer):
    def __init__(self, func_name: str, new_param: str):
        self.func_name = func_name
        # Parse the new parameter to ensure it’s a valid CST node
        self.new_param = cst.parse_expression(new_param)
        self.param_added = False

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        # Check if the function call name matches the target function
        if (
            isinstance(original_node.func, cst.Name)
            and original_node.func.value == self.func_name
        ):  # noqa
            # Add the new parameter to the function call arguments
            new_args = updated_node.args + (cst.Arg(value=self.new_param),)
            self.param_added = True
            return updated_node.with_changes(args=new_args)
        return updated_node


def add_param_to_function_call(
    original_code: str, func_name: str, new_param: str
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = FunctionCallParamAdder(func_name, new_param)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the function call is not found
    if not transformer.param_added:
        raise ValueError(
            f"Function call to {func_name} not found in the provided code."
        )
    # Return the modified code
    return modified_module.code
