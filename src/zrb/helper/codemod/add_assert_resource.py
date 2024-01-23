import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
def add_assert_resource(code: str, resource: str) -> str:
    """
    Adds an assertion statement to the end of a module that checks whether
    a resource has been successfully loaded.

    Args:
        code (str): The code of the module to modify.
        resoource (str): The name of the resource to check.

    Returns:
        str: The modified code with the new assertion statement added.
    """

    module = cst.parse_module(code)

    # Create the new assertion statement
    new_assert = cst.SimpleStatementLine(
        [
            cst.Assert(test=cst.Name(value=resource), msg=None),
        ]
    )

    module.body.append(new_assert)

    # Generate the modified code
    modified_code = module.code
    return modified_code
