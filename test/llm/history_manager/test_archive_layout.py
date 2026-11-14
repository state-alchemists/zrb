"""The pointer a summary writes to name its archive, and the search that finds it.

These two halves have no caller in common: the summarizer writes the prose, the
history manager reads transcripts for it, and nothing joined them but the regex
matching the sentence. A test that hand-wrote the pointer kept passing while a
reworded writer stopped being found. Each test here renders with the writer and
searches with the reader, so the pair cannot drift apart silently.
"""

import os

from zrb.llm.history_manager.archive_layout import (
    archive_names_in,
    render_archive_pointer,
    tool_results_dir,
    tool_results_names_in,
    verbatim_archive_path,
)


def test_the_pointer_names_the_archive_it_was_written_for():
    path = verbatim_archive_path("bold-arch-1234")
    assert archive_names_in(render_archive_pointer(path)) == {
        os.path.basename(path)
    }


def test_a_session_name_with_a_space_survives_the_round_trip():
    path = verbatim_archive_path("my session")
    assert archive_names_in(render_archive_pointer(path)) == {"my session.md"}


def test_a_windows_pointer_is_read_the_same_way():
    note = render_archive_pointer(r"C:\Users\go\.zrb\llm-history\verbatim\go.md")
    assert archive_names_in(note) == {"go.md"}


def test_a_pruned_tool_results_directory_is_read_off_its_block():
    archive = verbatim_archive_path("go")
    directory = tool_results_dir(archive)
    block = (
        "PRUNED TOOL RESULT (zrb): 3 of 9 tokens kept.\n\n"
        f'Full output: `{os.path.join(directory, "call-abc-1234.txt")}`'
    )
    assert tool_results_names_in(block) == {os.path.basename(directory)}


def test_one_summary_naming_both_kinds_is_read_once_each():
    archive = verbatim_archive_path("go")
    directory = tool_results_dir(archive)
    summary = (
        render_archive_pointer(archive)
        + "\n\n"
        + f"Full output: `{os.path.join(directory, 'call-abc-1234.txt')}`"
    )
    assert archive_names_in(summary) == {os.path.basename(archive)}
    assert tool_results_names_in(summary) == {os.path.basename(directory)}


def test_a_summary_without_a_pointer_names_nothing():
    assert archive_names_in("## Summary\n\nThe user asked for tests.") == set()
    assert tool_results_names_in("## Summary\n\nThe user asked for tests.") == set()
