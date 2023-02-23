import libcst as cst


def add_assert_module(code: str, import_alias: str) -> str:
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
