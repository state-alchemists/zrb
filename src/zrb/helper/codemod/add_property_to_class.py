import libcst as cst

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Optional


@typechecked
class AddPropertyTransformer(cst.CSTTransformer):
    def __init__(
        self,
        class_name: str,
        property_name_node: cst.Name,
        property_type_node: cst.Annotation,
        property_value_node: Optional[cst.BaseExpression],
    ):
        self.class_name = class_name
        self.property_name_node = property_name_node
        self.property_type_node = property_type_node
        self.property_value_node = property_value_node
        super().__init__()

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if updated_node.name.value != self.class_name:
            return updated_node
        class_body_statements = []
        if not isinstance(original_node.body, cst.EmptyLine):
            for stmt in original_node.body.body:
                if (
                    hasattr(stmt, "body")
                    and not isinstance(stmt.body, cst.IndentedBlock)
                    and len(stmt.body) > 0
                    and isinstance(stmt.body[0], cst.Pass)
                ):
                    continue
                # Add all old class body except any `pass` statement
                class_body_statements.append(stmt)
        # Add new property to the class
        class_body_statements.append(
            cst.SimpleStatementLine(
                body=[
                    cst.AnnAssign(
                        target=self.property_name_node,
                        annotation=self.property_type_node,
                        value=self.property_value_node,
                    )
                ]
            )
        )
        new_body = cst.IndentedBlock(
            body=class_body_statements,
            indent=updated_node.body.indent,
        )
        return updated_node.with_changes(body=new_body)


@typechecked
def add_property_to_class(
    code: str,
    class_name: str,
    property_name: str,
    property_type: str,
    property_value: Optional[str] = None,
) -> str:
    module = cst.parse_module(code)
    property_name_node = cst.Name(value=property_name)
    property_type_node = _get_property_type_node(property_type)
    property_value_node = _get_property_value_node(property_value)
    transformed_module = module.visit(
        AddPropertyTransformer(
            class_name=class_name,
            property_name_node=property_name_node,
            property_type_node=property_type_node,
            property_value_node=property_value_node,
        )
    )
    return transformed_module.code


def _get_property_type_node(property_type: str) -> cst.Annotation:
    if property_type.startswith("Optional[") and property_type.endswith("]"):
        inner_type = property_type[len("Optional[") : -1]
        return cst.Annotation(
            annotation=cst.Subscript(
                value=cst.Name("Optional"),
                slice=[
                    cst.SubscriptElement(
                        slice=cst.Index(value=cst.Name(value=inner_type))
                    )
                ],
            )
        )
    else:
        return cst.Annotation(cst.Name(value=property_type))


def _get_property_value_node(
    property_value: Optional[str],
) -> Optional[cst.BaseExpression]:
    if property_value is None:
        return None
    return cst.parse_expression(property_value)
