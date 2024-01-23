import libcst as cst

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Optional, Tuple, Union


@typechecked
def add_import_module(
    code: str,
    module_path: str,
    resource: Optional[str] = None,
    alias: Optional[str] = None,
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
        resource: An optional name of resource to be immported.
        alias: An optional alias to use for the imported module/resource.

    Returns:
        The modified code, as a string.
    """
    module = cst.parse_module(code)
    new_import = _get_new_import(
        module_path=module_path, resource=resource, alias=alias
    )

    last_import_index = None
    for i, node in enumerate(module.body):
        if isinstance(node, cst.SimpleStatementLine) and (
            isinstance(node.body[0], cst.Import)
            or isinstance(node.body[0], cst.ImportFrom)
        ):
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


def _get_new_import(
    module_path: str, resource: Optional[str] = None, alias: Optional[str] = None
) -> Union[cst.ImportFrom, cst.Import]:
    dots, module_path = _split_module_path(module_path)
    relative = [cst.Dot()] * len(dots)
    if resource is None:
        if len(relative) > 0:
            raise Exception("Relative import is not allowed, please specify resource")
        return cst.Import(
            names=[
                cst.ImportAlias(
                    name=cst.parse_expression(module_path), asname=_get_as_name(alias)
                )
            ],
        )
    return cst.ImportFrom(
        module=cst.parse_expression(module_path),
        names=[cst.ImportAlias(name=cst.Name(resource), asname=_get_as_name(alias))],
        relative=relative,
    )


@typechecked
def _split_module_path(module_path) -> Tuple[str, str]:
    prefix = ""
    suffix = ""
    is_prefix = True
    for char in module_path:
        if char != ".":
            is_prefix = False
        if is_prefix:
            prefix += char
            continue
        suffix += char
    return prefix, suffix


def _get_as_name(alias: Optional[str] = None) -> Optional[cst.AsName]:
    if alias is None:
        return None
    return cst.AsName(name=cst.Name(alias))
