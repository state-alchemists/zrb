import libcst as cst


class DictionaryModifier(cst.CSTTransformer):
    def __init__(self, dictionary_name: str, new_key: str, new_value: str):
        self.dictionary_name = dictionary_name
        self.new_key = new_key
        self.new_value = new_value
        self.found = False

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign:
        # Extract the first target from updated_node, which will be an AssignTarget
        target = updated_node.targets[0]
        # Check if the target is a Name (which should represent the dictionary)
        if (
            isinstance(target.target, cst.Name)
            and target.target.value == self.dictionary_name
        ):
            # Check if it's a dictionary initialization (e.g., my_dict = {...})
            if isinstance(updated_node.value, cst.Dict):
                self.found = True
                # Add new key-value pair to the existing dictionary
                new_entries = updated_node.value.elements + (
                    cst.DictElement(
                        key=cst.SimpleString(f'"{self.new_key}"'),
                        value=cst.SimpleString(f'"{self.new_value}"'),
                    ),
                )
                new_dict = updated_node.value.with_changes(elements=new_entries)
                return updated_node.with_changes(value=new_dict)
        return updated_node


def add_key_to_dict(
    original_code: str, dictionary_name: str, new_key: str, new_value: str
) -> str:
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = DictionaryModifier(dictionary_name, new_key, new_value)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the dictionary is not found
    if not transformer.found:
        raise ValueError(
            f"Dictionary {dictionary_name} not found in the provided code."
        )
    # Return the modified code
    return modified_module.code
