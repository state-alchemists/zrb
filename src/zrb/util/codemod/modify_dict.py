import libcst as cst

from zrb.util.codemod.modification_mode import APPEND, PREPEND


def prepend_key_to_dict(
    original_code: str, dictionary_name: str, new_key: str, new_value: str
) -> str:
    """
    Prepend a new key-value pair to a dictionary in the provided code.

    Args:
        original_code (str): The original Python code as a string.
        dictionary_name (str): The name of the dictionary variable.
        new_key (str): The key to prepend.
        new_value (str): The value for the new key.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified dictionary is not found in the code.
    """
    return _modify_dict(original_code, dictionary_name, new_key, new_value, PREPEND)


def append_key_to_dict(
    original_code: str, dictionary_name: str, new_key: str, new_value: str
) -> str:
    """
    Append a new key-value pair to a dictionary in the provided code.

    Args:
        original_code (str): The original Python code as a string.
        dictionary_name (str): The name of the dictionary variable.
        new_key (str): The key to append.
        new_value (str): The value for the new key.

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified dictionary is not found in the code.
    """
    return _modify_dict(original_code, dictionary_name, new_key, new_value, APPEND)


def _modify_dict(
    original_code: str, dictionary_name: str, new_key: str, new_value: str, mode: int
) -> str:
    """
    Modify a dictionary in the provided code by adding a new key-value pair.

    Args:
        original_code (str): The original Python code as a string.
        dictionary_name (str): The name of the dictionary variable.
        new_key (str): The key to add.
        new_value (str): The value for the new key.
        mode (int): The modification mode (PREPEND or APPEND).

    Returns:
        str: The modified Python code as a string.

    Raises:
        ValueError: If the specified dictionary is not found in the code.
    """
    # Parse the original code into a module
    module = cst.parse_module(original_code)
    # Initialize the transformer with the necessary information
    transformer = _DictionaryModifier(dictionary_name, new_key, new_value, mode)
    # Apply the transformation
    modified_module = module.visit(transformer)
    # Error handling: raise an error if the dictionary is not found
    if not transformer.found:
        raise ValueError(
            f"Dictionary {dictionary_name} not found in the provided code."
        )
    # Return the modified code
    return modified_module.code


class _DictionaryModifier(cst.CSTTransformer):
    """
    A LibCST transformer to modify a dictionary by adding a new key-value pair.
    """

    def __init__(self, dictionary_name: str, new_key: str, new_value: str, mode: int):
        """
        Initialize the transformer.

        Args:
            dictionary_name (str): The name of the target dictionary variable.
            new_key (str): The key to add.
            new_value (str): The value for the new key.
            mode (int): The modification mode (PREPEND or APPEND).
        """
        self.dictionary_name = dictionary_name
        self.new_key = new_key
        self.new_value = new_value
        self.found = False
        self.mode = mode

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign:
        """
        Called when leaving an Assign node. Modifies the dictionary if the target matches.
        """
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
                if self.mode == PREPEND:
                    new_entries = (
                        cst.DictElement(
                            key=cst.SimpleString(f'"{self.new_key}"'),
                            value=cst.SimpleString(f'"{self.new_value}"'),
                        ),
                    ) + updated_node.value.elements
                    new_dict = updated_node.value.with_changes(elements=new_entries)
                    return updated_node.with_changes(value=new_dict)
                if self.mode == APPEND:
                    new_entries = updated_node.value.elements + (
                        cst.DictElement(
                            key=cst.SimpleString(f'"{self.new_key}"'),
                            value=cst.SimpleString(f'"{self.new_value}"'),
                        ),
                    )
                    new_dict = updated_node.value.with_changes(elements=new_entries)
                    return updated_node.with_changes(value=new_dict)
        return updated_node
