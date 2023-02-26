import libcst as cst


def add_assert_module(code: str, import_alias: str) -> str:
    """
    Adds an assertion statement to the end of a module that checks whether
    a given import has been successfully loaded.

    Args:
        code (str): The code of the module to modify.
        import_alias (str): The name of the alias used to import
            the module to check.

    Returns:
        str: The modified code with the new assertion statement added.
    """

    module = cst.parse_module(code)

    # Create the new assertion statement
    new_assert = cst.SimpleStatementLine([
        cst.Assert(
            test=cst.Name(value=import_alias),
            msg=None
        ),
    ])

    module.body.append(new_assert)

    # Generate the modified code
    modified_code = module.code
    return modified_code
