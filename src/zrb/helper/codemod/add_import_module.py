import libcst as cst


def add_import_module(code: str, module_path: str) -> str:
    module = cst.parse_module(code)

    # Create the new import statement
    new_import = cst.Import(
        names=[
            cst.ImportAlias(
                name=cst.parse_expression(module_path),
                asname=None
            )
        ],
    )

    last_import_index = None
    for i, node in enumerate(module.body):
        if isinstance(
            node, cst.SimpleStatementLine
        ) and isinstance(node.body[0], cst.Import):
            last_import_index = i

    # If there are no import statements
    # # add the new import at the beginning of the module
    if last_import_index is None:
        module.body.insert(0, cst.EmptyLine())
        module.body.insert(0, cst.EmptyLine())
        module.body.insert(0, new_import)
    else:
        module.body.insert(last_import_index + 1, cst.EmptyLine())
        module.body.insert(last_import_index + 1, new_import)

    # Generate the modified code
    modified_code = module.code
    return modified_code
