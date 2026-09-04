"""Ratchet for the test-file split rule (AGENTS.md → Test Guidelines: split
files over 500 lines by feature group).

The rule was documented and unenforced, so 46 files had already crossed it —
`llm/agent/run/test_runner.py` at 2049 lines, four times over. Splitting all
46 in one sweep would move ~30k lines of other people's tests for no
behavioral gain, so this holds the line in the direction that matters
instead: a **new** test file cannot be born over the limit, and an existing
offender can only shrink.

Each baseline below is the file's line count at the time this ratchet landed,
rounded up to the next 50 — headroom for an ordinary edit, not for another
feature group. When you do split one, delete its entry (or lower it); when a
split genuinely cannot happen, say why here rather than raising the number.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
TEST_ROOT = REPO_ROOT / "test"

MAX_TEST_FILE_LINES = 500

# Path relative to test/ -> max line count. Lower these as files get split;
# never add a new entry — a new file over the limit is the thing this guards.
GRANDFATHERED_BUDGETS = {
    "builtin/test_git.py": 600,
    "config/test_config_setters.py": 700,
    "llm/agent/run/test_deferred_calls.py": 1150,
    "llm/agent/run/test_history_utils.py": 850,
    "llm/agent/run/test_runner.py": 2050,
    "llm/agent/subagent/test_live_session.py": 800,
    "llm/agent/subagent/test_manager.py": 550,
    "llm/agent/test_common.py": 1200,
    "llm/approval/test_approval_channel.py": 900,
    "llm/config/test_limiter.py": 1000,
    "llm/history_manager/test_file_history_manager.py": 1100,
    "llm/hook/test_manager.py": 750,
    "llm/hook/test_manager_functionality.py": 700,
    "llm/lsp/test_manager.py": 750,
    "llm/skill/test_skill_manager.py": 1050,
    "llm/snapshot/test_manager.py": 600,
    "llm/summarizer/history_processor/test_history_summarizer.py": 900,
    "llm/summarizer/history_processor/test_tool_pair_safety.py": 550,
    "llm/task/chat/test_llm_chat_task.py": 650,
    "llm/task/chat/test_running.py": 600,
    "llm/tool/test_code.py": 550,
    "llm/tool/test_delegate_background.py": 600,
    "llm/tool/test_delegate_tool.py": 1750,
    "llm/tool/test_file.py": 1550,
    "llm/tool/test_journal.py": 750,
    "llm/tool/test_plan.py": 550,
    "llm/tool/test_rag.py": 950,
    "llm/tool/test_shell.py": 650,
    "llm/tool/test_web_tool.py": 800,
    "llm/ui/base/test_commands.py": 1000,
    "llm/ui/default/app/completion/test_completer.py": 600,
    "llm/ui/default/test_confirmation.py": 550,
    "llm/ui/default/test_keybindings.py": 1300,
    "llm/ui/default/test_output.py": 1050,
    "llm/ui/test_buffered_ui.py": 700,
    "llm/ui/test_multi_ui.py": 650,
    "llm/ui/test_ui_command_handlers.py": 950,
    "llm/util/test_camera.py": 600,
    "llm/util/test_clipboard.py": 600,
    "llm/util/test_stream_response.py": 1200,
    "llm/voice/test_engine.py": 750,
    "runner/chat/test_chat_session_manager.py": 1050,
    "session/test_session.py": 700,
    "task/base/test_execution.py": 750,
    "task/base/test_monitoring.py": 550,
    "util/cmd/test_command.py": 850,
}


def _line_count(path: Path) -> int:
    return len(path.read_text().splitlines())


def test_no_new_test_file_exceeds_the_split_threshold():
    offenders = {
        str(p.relative_to(TEST_ROOT)): _line_count(p)
        for p in TEST_ROOT.rglob("test_*.py")
        if _line_count(p) > MAX_TEST_FILE_LINES
    }
    unlisted = {k: v for k, v in offenders.items() if k not in GRANDFATHERED_BUDGETS}
    assert not unlisted, (
        "New test file(s) over "
        f"{MAX_TEST_FILE_LINES} lines: {unlisted}. Split by feature group "
        "(AGENTS.md → Test Guidelines) rather than adding to "
        "GRANDFATHERED_BUDGETS."
    )


def test_grandfathered_test_files_do_not_grow():
    grown = {}
    for rel, budget in GRANDFATHERED_BUDGETS.items():
        path = TEST_ROOT / rel
        assert path.exists(), (
            f"{rel} is in GRANDFATHERED_BUDGETS but does not exist — "
            "it was renamed or split; drop the stale entry."
        )
        count = _line_count(path)
        if count > budget:
            grown[rel] = (count, budget)
    assert not grown, (
        f"Grandfathered test file(s) grew past their budget: {grown}. "
        "Split off the new feature group instead of raising the number."
    )
