import libcst as cst


class ClassPropertyAdder(cst.CSTTransformer):
    def __init__(
        self, class_name: str, property_name: str, annotation: str, default_value: str
    ):
        self.class_name = class_name
        self.property_name = property_name
        self.annotation = cst.Annotation(cst.parse_expression(annotation))
        self.default_value = cst.parse_expression(default_value)
        self.class_found = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Check if this is the target class
        if original_node.name.value == self.class_name:
            self.class_found = True
            # Create the annotated property with a default value
            new_property = cst.SimpleStatementLine(
                body=[
                    cst.AnnAssign(
                        target=cst.Name(self.property_name),
                        annotation=self.annotation,
                        value=self.default_value,
                    )
                ]
            )
            # Insert the new property at the start of the class body with a newline
            new_body = cst.IndentedBlock(body=(new_property,) + updated_node.body.body)
            return updated_node.with_changes(body=new_body)
        return updated_node


def add_property_to_class(
    original_code: str,
    class_name: str,
    property_name: str,
    annotation: str,
    default_value: str,
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize transformer with the class name, property name, annotation, and default value
    transformer = ClassPropertyAdder(
        class_name, property_name, annotation, default_value
    )
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Check if the class was found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    # Return the modified code
    return modified_module.code
