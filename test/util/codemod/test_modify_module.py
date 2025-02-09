import textwrap

from zrb.util.codemod.modify_module import prepend_code_to_module

original_code = """
import numpy as np
import pandas as pd
from fastapi import FastAPI
b = 7
""".strip()


def test_prepend_code_to_module():
    new_code = prepend_code_to_module(original_code, "a = 5")
    assert (
        new_code
        == textwrap.dedent(
            """
        import numpy as np
        import pandas as pd
        from fastapi import FastAPI
        a = 5
        b = 7
        """
        ).strip()
    )


def test_prepend_code_to_empty_module():
    new_code = prepend_code_to_module("", "a = 5")
    assert new_code == "a = 5"
