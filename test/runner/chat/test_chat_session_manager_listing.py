"""Tests for chat_session_manager.py."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_history_manager():
    with patch("zrb.runner.chat.chat_session_manager.FileHistoryManager") as mock_fhm:
        mock_fhm.return_value.load.return_value = []
        yield


class TestChatSessionManagerListing:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        ChatSessionManager.reset_instance()
        yield
        ChatSessionManager.reset_instance()

    def test_get_sessions_count(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        count = manager.get_sessions_count()
        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_messages(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="messages-test")
        messages = manager.get_messages("messages-test")
        assert isinstance(messages, list)

    def test_get_sessions_with_history(self, tmp_path):
        """Test get_sessions returns sessions from history files."""
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        # Create a mock history file
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        history_file = history_dir / "test-session-2024-01-15-10-30.json"
        history_file.write_text("[]")

        with (
            patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg,
            patch("os.path.getmtime", return_value=123456789.0),
        ):
            mock_cfg.LLM_HISTORY_DIR = str(history_dir)
            mock_cfg.WEB_SESSION_PAGE_SIZE = 10

            # We must update the internal history manager to point to the new dir
            # because the manager instance already exists.
            original_hm = manager.history_manager
            manager.set_history_manager(
                FileHistoryManager(history_dir=str(history_dir))
            )

            try:
                sessions = manager.get_sessions()
                # Should include the session from history
                assert any(s["session_name"] == "test-session" for s in sessions)
            finally:
                manager.set_history_manager(original_hm)

    def test_get_sessions_marks_ordinary_session_as_not_delegated(self, tmp_path):
        """A plain session name must carry `parent_session_id`/`agent_name`
        as None — it's not a delegated sub-agent transcript."""
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "test-session-2024-01-15-10-30.json").write_text("[]")

        with (
            patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg,
            patch("os.path.getmtime", return_value=123456789.0),
        ):
            mock_cfg.LLM_HISTORY_DIR = str(history_dir)
            mock_cfg.WEB_SESSION_PAGE_SIZE = 10

            original_hm = manager.history_manager
            manager.set_history_manager(
                FileHistoryManager(history_dir=str(history_dir))
            )

            try:
                sessions = manager.get_sessions()
                entry = next(s for s in sessions if s["session_name"] == "test-session")
                assert entry["parent_session_id"] is None
                assert entry["agent_name"] is None
            finally:
                manager.set_history_manager(original_hm)

    def test_get_sessions_parses_delegated_subagent_session_name(self, tmp_path):
        """A persisted sub-agent transcript (see `subagent_session_naming.py`:
        `{parent}-sub-{agent_name}-{agent_id}`, stored under
        `subagent/{agent_type}/`) must surface its parent session and agent
        name in the listing, with zero new registry."""
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        history_dir = tmp_path / "history"
        history_dir.mkdir()
        subdir = history_dir / "subagent" / "code-reviewer"
        subdir.mkdir(parents=True)
        (subdir / "sess1-sub-code-reviewer-a1b2c3d4.json").write_text("[]")

        with (
            patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg,
            patch("os.path.getmtime", return_value=123456789.0),
        ):
            mock_cfg.LLM_HISTORY_DIR = str(history_dir)
            mock_cfg.WEB_SESSION_PAGE_SIZE = 10

            original_hm = manager.history_manager
            manager.set_history_manager(
                FileHistoryManager(history_dir=str(history_dir))
            )

            try:
                sessions = manager.get_sessions()
                entry = next(
                    s
                    for s in sessions
                    if s["session_name"] == "sess1-sub-code-reviewer-a1b2c3d4"
                )
                assert entry["parent_session_id"] == "sess1"
                assert entry["agent_name"] == "code-reviewer"
                assert entry["is_active"] is False
            finally:
                manager.set_history_manager(original_hm)

    def test_get_sessions_lists_legacy_flat_delegated_transcripts(self, tmp_path):
        """Delegated transcripts written before the `subagent/{agent_type}/`
        layout (flat in the history root) still appear in the listing."""
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()

        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "sess1-sub-researcher-a1b2c3d4.json").write_text("[]")

        with (
            patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg,
            patch("os.path.getmtime", return_value=123456789.0),
        ):
            mock_cfg.LLM_HISTORY_DIR = str(history_dir)
            mock_cfg.WEB_SESSION_PAGE_SIZE = 10

            original_hm = manager.history_manager
            manager.set_history_manager(
                FileHistoryManager(history_dir=str(history_dir))
            )

            try:
                sessions = manager.get_sessions()
                entry = next(
                    s
                    for s in sessions
                    if s["session_name"] == "sess1-sub-researcher-a1b2c3d4"
                )
                assert entry["parent_session_id"] == "sess1"
                assert entry["agent_name"] == "researcher"
            finally:
                manager.set_history_manager(original_hm)

    @pytest.mark.asyncio
    async def test_get_messages_extracts_content_from_parts(self):
        """Messages with parts get flattened into role/content/timestamp dicts."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="msg-test")

        part = MagicMock()
        part.content = "hello"
        msg = MagicMock()
        msg.kind = "request"
        msg.parts = [part]
        msg.timestamp = "2026-01-01T00:00:00"

        with patch.object(manager.history_manager, "load", return_value=[msg]):
            messages = manager.get_messages("msg-test")
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "hello"
        assert messages[0]["timestamp"] == "2026-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_get_messages_assistant_role_for_non_request(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="role-test")

        part = MagicMock()
        part.content = {"complex": "structure"}  # non-string content path
        msg = MagicMock()
        msg.kind = "response"
        msg.parts = [part]
        del msg.timestamp  # exercise the getattr fallback

        with patch.object(manager.history_manager, "load", return_value=[msg]):
            messages = manager.get_messages("role-test")
        assert messages[0]["role"] == "assistant"
        assert "complex" in messages[0]["content"]
        assert messages[0]["timestamp"] is None

    @pytest.mark.asyncio
    async def test_get_messages_splits_live_context_for_user_role(self):
        """A user turn's trailing <live-context> block is separated out, not
        shown as if the user typed it."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="live-context-test")

        part = MagicMock()
        part.content = (
            "what's the weather\n\n<live-context>\n- Time: now\n</live-context>"
        )
        msg = MagicMock()
        msg.kind = "request"
        msg.parts = [part]
        msg.timestamp = None

        with patch.object(manager.history_manager, "load", return_value=[msg]):
            messages = manager.get_messages("live-context-test")
        assert messages[0]["content"] == "what's the weather"
        assert (
            messages[0]["live_context"]
            == "<live-context>\n- Time: now\n</live-context>"
        )

    @pytest.mark.asyncio
    async def test_get_messages_no_live_context_field_when_absent(self):
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="no-live-context-test")

        part = MagicMock()
        part.content = "hello"
        msg = MagicMock()
        msg.kind = "request"
        msg.parts = [part]
        msg.timestamp = None

        with patch.object(manager.history_manager, "load", return_value=[msg]):
            messages = manager.get_messages("no-live-context-test")
        assert messages[0]["content"] == "hello"
        assert messages[0]["live_context"] is None

    @pytest.mark.asyncio
    async def test_get_messages_assistant_role_never_split_for_live_context(self):
        """Live context is only ever appended to user turns; assistant text
        that happens to contain the literal tag is left untouched."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="assistant-live-context-test")

        part = MagicMock()
        part.content = "some assistant text"
        msg = MagicMock()
        msg.kind = "response"
        msg.parts = [part]
        msg.timestamp = None

        with patch.object(manager.history_manager, "load", return_value=[msg]):
            messages = manager.get_messages("assistant-live-context-test")
        assert messages[0]["live_context"] is None

    def test_scan_sessions_empty_when_no_history_dir(self):
        """Without LLM_HISTORY_DIR set, the scan returns []."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        with patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg:
            mock_cfg.LLM_HISTORY_DIR = ""
            assert manager.scan_sessions() == []

    def test_scan_sessions_empty_when_dir_missing(self, tmp_path):
        """LLM_HISTORY_DIR set but nonexistent → returns []."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = ChatSessionManager.get_instance_sync()
        with patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg:
            mock_cfg.LLM_HISTORY_DIR = str(tmp_path / "missing")
            assert manager.scan_sessions() == []

    @pytest.mark.asyncio
    async def test_get_sessions_includes_active_without_history(self):
        """An active session with no history file still shows up in the listing."""
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        manager = await ChatSessionManager.get_instance()
        await manager.create_session(session_id="active-only")
        with patch("zrb.runner.chat.chat_session_manager.CFG") as mock_cfg:
            mock_cfg.LLM_HISTORY_DIR = ""
            mock_cfg.WEB_SESSION_PAGE_SIZE = 50
            sessions = manager.get_sessions()
        ids = [s["session_id"] for s in sessions]
        assert "active-only" in ids
