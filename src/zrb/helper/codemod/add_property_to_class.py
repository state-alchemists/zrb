import libcst as cst


class AddPropertyTransformer(cst.CSTTransformer):
    def __init__(self, class_name: str, property_name: str, property_type: str):
        self.class_name = class_name
        self.property_name = property_name
        self.property_type = property_type
        super().__init__()

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if updated_node.name.value == self.class_name:
            new_stmt = cst.SimpleStatementLine(
                body=[
                    cst.AnnAssign(
                        target=cst.Name(value=self.property_name),
                        annotation=cst.Annotation(
                            cst.Name(value=self.property_type)
                        ),
                        value=None,
                    )
                ]
            )
            new_body = cst.IndentedBlock(
                body=updated_node.body.body + (new_stmt,),
                indent=updated_node.body.indent,
            )
            return updated_node.with_changes(body=new_body)
        return updated_node


def add_property_to_class(
    code: str, class_name: str, property_name: str, property_type: str
) -> str:
    module = cst.parse_module(code)
    transformed_module = module.visit(
        AddPropertyTransformer(class_name, property_name, property_type)
    )
    return transformed_module.code
