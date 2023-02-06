import libcst as cst


def add_assert_module(code: str, module_path: str) -> str:
    module = cst.parse_module(code)

    # Create the new assertion statement
    new_assert = cst.SimpleStatementLine([
        cst.Assert(
            test=cst.Name(value=module_path.split(".")[-1]),
            msg=None
        ),
    ])

    module.body.append(new_assert)

    # Generate the modified code
    modified_code = module.code
    return modified_code
