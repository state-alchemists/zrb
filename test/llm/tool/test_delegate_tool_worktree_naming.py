import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import create_delegate_to_agent_tool


@pytest.fixture
def mock_sub_agent_manager():
    manager = MagicMock(spec=SubAgentManager)
    # Setup scan return value
    agent_def = SubAgentDefinition(
        name="test-agent",
        path="path",
        description="A test agent",
        system_prompt="prompt",
    )
    manager.scan.return_value = [agent_def]
    return manager


@pytest.mark.asyncio
async def test_isolate_worktree_uses_distinct_branch_names_per_task(
    mock_sub_agent_manager,
):
    """Concurrent isolate_worktree tasks must not collide on enter_worktree's
    own (second-granularity) default branch name."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch("zrb.llm.tool.delegate.get_active_worktree", return_value="/wt"),
        patch("zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock),
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_enter.return_value = "Worktree created"
        mock_run_agent.return_value = ("done", [])
        await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                },
                {
                    "agent_name": "test-agent",
                    "deliverable": "d2",
                    "task": "t2",
                    "non_goals": [],
                    "isolate_worktree": True,
                },
            ]
        )

    branch_names = [c.kwargs["branch_name"] for c in mock_enter.await_args_list]
    assert len(branch_names) == 2
    assert len(set(branch_names)) == 2


@pytest.mark.asyncio
async def test_subagent_history_persisted(mock_sub_agent_manager, monkeypatch):
    """Every completed delegation persists its transcript; no knob gates it."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch("zrb.llm.tool.delegate.get_current_tool_session", return_value="sess1"),
        patch("zrb.llm.tool.delegate.persist_subagent_history") as mock_persist,
    ):
        mock_run_agent.return_value = ("ok", [{"fake": "message"}])
        result = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    mock_persist.assert_called_once()
    conversation_name, history = mock_persist.call_args.args
    assert conversation_name.startswith("sess1-sub-test-agent-")
    assert history == [{"fake": "message"}]
    assert f"Transcript saved as '{conversation_name}'" in result


@pytest.mark.asyncio
async def test_subagent_history_persist_failure_does_not_break_delegation(
    mock_sub_agent_manager, monkeypatch
):
    """A persistence error (disk full, permissions) must not surface as a
    delegation failure — best-effort, same posture as the hook firing."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.history_manager.file_history_manager.FileHistoryManager",
            side_effect=OSError("disk full"),
        ),
    ):
        mock_run_agent.return_value = ("ok", [])
        result = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    assert "completed:" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_fan_out_persists_history_per_task(mock_sub_agent_manager, monkeypatch):
    """Fan-out shares `run_agent_task`, so each task gets its own persisted
    transcript under a distinct conversation name."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch("zrb.llm.tool.delegate.get_current_tool_session", return_value="sess1"),
        patch("zrb.llm.tool.delegate.persist_subagent_history") as mock_persist,
    ):
        mock_run_agent.side_effect = [("Result A", []), ("Result B", [])]
        await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "a",
                    "task": "ta",
                    "non_goals": [],
                },
                {
                    "agent_name": "test-agent",
                    "deliverable": "b",
                    "task": "tb",
                    "non_goals": [],
                },
            ]
        )

    assert mock_persist.call_count == 2
    names = {c.args[0] for c in mock_persist.call_args_list}
    assert len(names) == 2  # distinct conversation names per task


@pytest.mark.asyncio
async def test_activity_start_and_finish_are_scoped_to_the_current_session(
    mock_sub_agent_manager,
):
    """A process hosting multiple sessions must not bleed one session's
    running sub-agents into another's activity panel/listing."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.get_session_ownership_key",
            return_value="chat-session-42",
        ),
        patch(
            "zrb.llm.tool.delegate.get_current_tool_session",
            return_value="display-session-42",
        ),
        patch("zrb.llm.tool.delegate.agent_activity_registry") as mock_registry,
    ):
        mock_run_agent.return_value = ("ok", [])
        await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])

    mock_registry.start.assert_called_once()
    assert mock_registry.start.call_args.kwargs["session_id"] == "chat-session-42"
    mock_registry.finish.assert_called_once()
    assert mock_registry.finish.call_args.kwargs["session_id"] == "chat-session-42"


@pytest.mark.asyncio
async def test_single_delegate_does_not_flush_routine_output_to_main(
    mock_sub_agent_manager,
):
    """A sub-agent's routine buffered output (search queries, fetch status)
    must not be dumped into the main transcript on completion -- only the
    tool's own result reaches the main agent (as the tool-call return value,
    a separate mechanism from the UI transcript)."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    parent_ui = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    async def run_and_write_to_buffer(*args, ui=None, **kwargs):
        # Simulate the sub-agent producing routine output during its run.
        if ui is not None:
            ui.append_to_output("searching for things...")
        return "done", []

    with (
        patch("zrb.llm.tool.delegate.run_agent", side_effect=run_and_write_to_buffer),
        patch("zrb.llm.tool.delegate.get_current_ui", return_value=parent_ui),
    ):
        await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])

    parent_ui.append_to_output.assert_not_called()


def testpersist_subagent_history_does_not_grow_unbounded(tmp_path, monkeypatch):
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "10")

    for _ in range(200):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    subdir = tmp_path / "subagent" / "researcher"
    assert list(subdir.iterdir())
    assert len(list(subdir.iterdir())) == 10


def testpersist_subagent_history_writes_no_backup(tmp_path, monkeypatch):
    """Each conversation_name is unique and written exactly once -- a backup
    of a session that's never resaved doubles disk usage for no recovery
    value."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv(
        "ZRB_LLM_HISTORY_BACKUP_RETAIN", "-1"
    )  # keep-all, if any were written

    name = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    persist_subagent_history(name, [])

    assert len(list((tmp_path / "subagent" / "researcher").iterdir())) == 1
    # Nothing flat in the history root: only the subagent/ directory tree.
    assert [p for p in tmp_path.iterdir() if p.is_file()] == []


def testpersist_subagent_history_never_prunes_ordinary_conversations(
    tmp_path, monkeypatch
):
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "3")

    real_conversation = tmp_path / "my-real-conversation.json"
    real_conversation.write_text("[]")

    for _ in range(20):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    assert real_conversation.exists()
    subdir = tmp_path / "subagent" / "researcher"
    assert len(list(subdir.iterdir())) == 3


def testpersist_subagent_history_retain_minus_one_disables_pruning(
    tmp_path, monkeypatch
):
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "-1")

    for _ in range(15):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    assert len(list((tmp_path / "subagent" / "researcher").iterdir())) == 15


def testpersist_subagent_history_keeps_most_recently_written(tmp_path, monkeypatch):
    """Pruning must drop the oldest, not an arbitrary subset."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "2")

    names = []
    for i in range(4):
        name = format_delegated_session_name("sess1", "researcher", f"{i:08x}")
        names.append(name)
        persist_subagent_history(name, [])
        # Force distinct mtimes even on filesystems with coarse granularity.
        stamp = float(i)
        os.utime(tmp_path / "subagent" / "researcher" / f"{name}.json", (stamp, stamp))

    subdir = tmp_path / "subagent" / "researcher"
    remaining = {p.stem for p in subdir.iterdir()}
    assert remaining == {names[2], names[3]}


def testpersist_subagent_history_layout_groups_by_agent_type(tmp_path, monkeypatch):
    """Delegated transcripts land under LLM_HISTORY_DIR/subagent/<agent-type>/
    — separate from main sessions (which stay flat in the history root)."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "-1")

    researcher = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    reviewer = format_delegated_session_name("sess1", "code-reviewer", "e5f6a7b8")
    persist_subagent_history(researcher, [])
    persist_subagent_history(reviewer, [])

    assert (tmp_path / "subagent" / "researcher" / f"{researcher}.json").exists()
    assert (tmp_path / "subagent" / "code-reviewer" / f"{reviewer}.json").exists()
    assert not (tmp_path / f"{researcher}.json").exists()
    assert not (tmp_path / f"{reviewer}.json").exists()


def testpersist_subagent_history_never_prunes_legacy_flat_files(tmp_path, monkeypatch):
    """Old-format delegated transcripts (flat in the history root, before the
    subagent/<agent-type>/ layout) are no longer pruning candidates.

    Pruning is scoped to subagent/<agent-type>/ only: the flat root also
    holds ordinary (non-delegated) sessions, and a name that merely *looks*
    delegated there (whether a genuine pre-layout legacy file or a user
    session that happens to collide with the naming shape) must never be a
    deletion candidate. Accepted cost: legacy flat files simply accumulate
    forever now, same as before this feature existed — read/search still see
    them (`subagent_history_directories`), only pruning stops.
    """
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "2")

    legacy = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    (tmp_path / f"{legacy}.json").write_text("[]")
    for _ in range(5):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    # The legacy flat file survives regardless of how many subagent/ writes
    # happen; the cap of 2 applies only within subagent/researcher/.
    assert (tmp_path / f"{legacy}.json").exists()
    total = len(list((tmp_path / "subagent" / "researcher").iterdir()))
    assert total == 2


def testpersist_subagent_history_never_prunes_colliding_root_session_name(
    tmp_path, monkeypatch
):
    """A user-named session sitting flat in the history root that happens to
    match the delegated naming shape (e.g. via `/save`) must never become a
    deletion candidate, regardless of how many delegated transcripts exist."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "1")

    # Matches `parse_delegated_session`'s shape but is an ordinary user
    # session, not something `persist_subagent_history` ever wrote.
    colliding_name = "myproj-sub-reviewer-1234abcd"
    (tmp_path / f"{colliding_name}.json").write_text("[]")

    for _ in range(10):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    assert (tmp_path / f"{colliding_name}.json").exists()
    assert len(list((tmp_path / "subagent" / "researcher").iterdir())) == 1
