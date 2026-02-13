import os
import tempfile

import pytest

from zrb.llm.note.manager import NoteManager
from zrb.llm.tool.note import (
    create_read_contextual_note_tool,
    create_read_long_term_note_tool,
    create_write_contextual_note_tool,
    create_write_long_term_note_tool,
)


@pytest.mark.asyncio
async def test_long_term_note_tools():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        note_manager = NoteManager(tmp_path)

        read_ltn = create_read_long_term_note_tool(note_manager)
        write_ltn = create_write_long_term_note_tool(note_manager)

        assert read_ltn.__name__ == "ReadLongTermNote"
        assert write_ltn.__name__ == "WriteLongTermNote"

        # Test Write
        await write_ltn("remember this")

        # Test Read
        content = await read_ltn()
        assert content == "remember this"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_contextual_note_tools():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        note_manager = NoteManager(tmp_path)

        read_ctx = create_read_contextual_note_tool(note_manager)
        write_ctx = create_write_contextual_note_tool(note_manager)

        assert read_ctx.__name__ == "ReadContextualNote"
        assert write_ctx.__name__ == "WriteContextualNote"

        cwd = os.getcwd()

        # Test Write
        await write_ctx("project note", cwd)

        # Test Read
        content = await read_ctx(cwd)
        assert content == "project note"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
