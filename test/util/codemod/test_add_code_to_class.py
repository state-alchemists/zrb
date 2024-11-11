from zrb.util.codemod.add_code_to_class import add_code_to_class

original_code = """
class OtherClass:
    def __init__(self):
        pass
def MyClass(x):
    pass
class MyClass:
    def __init__(self):
        self.value = 42
"""

method_code = """
def new_method(self):
    print("This is a new method")
"""

expected_new_code = """
class OtherClass:
    def __init__(self):
        pass
def MyClass(x):
    pass
class MyClass:
    def __init__(self):
        self.value = 42
    def new_method(self):
        print("This is a new method")
"""


def test_add_code_to_class():
    new_code = add_code_to_class(original_code.strip(), "MyClass", method_code.strip())
    assert new_code == expected_new_code.strip()
