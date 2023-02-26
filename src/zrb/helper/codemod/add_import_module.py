from typing import Optional
import libcst as cst


def add_import_module(
    code: str,
    module_path: str,
    import_alias: Optional[str] = None
) -> str:
    """
    Parses the given code as a module using `libcst.parse_module()`,
    and adds an import statement for the module at the given `module_path`,
    with an optional `import_alias`. If there are no existing import
    statements in the module, the new import statement will be added at the
    beginning of the module. Otherwise, the new import statement will be added
    immediately after the last existing import statement.

    Args:
        code: The code to modify.
        module_path: The path to the module to import, in dot notation.
        import_alias: An optional alias to use for the imported module.

    Returns:
        The modified code, as a string.
    """
    module = cst.parse_module(code)

    # Create the new import statement
    new_import = cst.Import(
        names=[
            cst.ImportAlias(
                name=cst.parse_expression(module_path),
                asname=cst.AsName(name=cst.parse_expression(import_alias))
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
