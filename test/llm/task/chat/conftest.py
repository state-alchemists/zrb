"""Register the presentation layer's session runner for these tests.

`ChatRunning.run_interactive_session` asks
`zrb.llm.shared.session_presentation` for the runner rather than importing
`zrb.llm.ui`, and `zrb llm chat` is what registers the real one. A test that
drives an interactive session stands where that command stands, so it
registers it too — and clears it afterwards, so a test that asserts the
refusal sees the seam empty.
"""

import pytest

from zrb.llm.shared.session_presentation import (
    clear_interactive_runner,
    register_interactive_runner,
)
from zrb.llm.ui.session import run_interactive_session


@pytest.fixture(autouse=True)
def interactive_runner():
    register_interactive_runner(run_interactive_session)
    yield run_interactive_session
    clear_interactive_runner()
