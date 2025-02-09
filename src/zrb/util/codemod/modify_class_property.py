import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND


def append_property_to_class(
    original_code: str,
    class_name: str,
    property_name: str,
    annotation: str,
    default_value: str,
) -> str:
    return _modify_class_property(
        original_code, class_name, property_name, annotation, default_value, APPEND
    )


def prepend_property_to_class(
    original_code: str,
    class_name: str,
    property_name: str,
    annotation: str,
    default_value: str,
) -> str:
    return _modify_class_property(
        original_code, class_name, property_name, annotation, default_value, PREPEND
    )


def _modify_class_property(
    original_code: str,
    class_name: str,
    property_name: str,
    annotation: str,
    default_value: str,
    mode: int,
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize transformer with the class name, property name, annotation, and default value
    transformer = _ClassPropertyModifier(
        class_name, property_name, annotation, default_value, mode
    )
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Check if the class was found
    if not transformer.class_found:
        raise ValueError(f"Class {class_name} not found in the provided code.")
    # Return the modified code
    return modified_module.code


class _ClassPropertyModifier(cst.CSTTransformer):
    def __init__(
        self,
        class_name: str,
        property_name: str,
        annotation: str,
        default_value: str,
        mode: int,
    ):
        self.class_name = class_name
        self.property_name = property_name
        self.annotation = cst.Annotation(cst.parse_expression(annotation))
        self.default_value = cst.parse_expression(default_value)
        self.class_found = False
        self.mode = mode

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
            if self.mode == PREPEND:
                new_body = cst.IndentedBlock(
                    body=(new_property,) + updated_node.body.body
                )
                return updated_node.with_changes(body=new_body)
            if self.mode == APPEND:
                # Identify properties and methods
                properties = []
                methods = []
                for stmt in updated_node.body.body:
                    if isinstance(stmt, cst.SimpleStatementLine) and isinstance(
                        stmt.body[0], (cst.AnnAssign, cst.Assign)
                    ):
                        properties.append(stmt)
                    elif isinstance(stmt, cst.FunctionDef):
                        methods.append(stmt)
                if properties:
                    # Class has properties
                    last_property_index = updated_node.body.body.index(properties[-1])
                    new_body = cst.IndentedBlock(
                        body=(
                            updated_node.body.body[: last_property_index + 1]
                            + (new_property,)
                            + updated_node.body.body[last_property_index + 1 :]
                        )
                    )
                    return updated_node.with_changes(body=new_body)
                if methods:
                    # Class doesn't have properties but has methods
                    first_method_index = updated_node.body.body.index(methods[0])
                    new_body = cst.IndentedBlock(
                        body=(
                            updated_node.body.body[:first_method_index]
                            + (new_property,)
                            + updated_node.body.body[first_method_index:]
                        )
                    )
                    return updated_node.with_changes(body=new_body)
                # Class is empty, add add the bottom
                new_body = cst.IndentedBlock(
                    body=updated_node.body.body + (new_property,)
                )
                return updated_node.with_changes(body=new_body)
        return updated_node
