"""Path resolution for the session state logger.

The logger builds every path from `get_session_log_dir`; a configured `~` must
be expanded there once, not only in the writer.
"""

import os

from zrb.session_state_logger.file_session_state_logger import (
    FileSessionStateLogger,
)


def test_get_session_log_dir_expands_a_tilde_once():
    """Every path the logger builds must agree on the expanded directory.

    `write`, `list`, `read` and pruning all call `get_session_log_dir`; a
    literal `~` there means the JSON is written under the literal directory
    while listing looks under `$HOME` (or the reverse).
    """
    expanded = os.path.expanduser("~/zrb-session-log-test")
    logger = FileSessionStateLogger("~/zrb-session-log-test")

    assert logger.get_session_log_dir() == expanded
    assert logger.get_session_file_path("session") == os.path.join(
        expanded, "session.json"
    )
