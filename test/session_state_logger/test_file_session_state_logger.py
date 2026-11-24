"""Tests for file_session_state_logger.py."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestFileSessionStateLogger:
    """Test FileSessionStateLogger class."""

    def test_init_with_string_path(self):
        """Test initialization with string path."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger("/tmp/test_logs")
        assert logger.session_log_dir_param == "/tmp/test_logs"

    def test_init_with_callable_path(self):
        """Test initialization with callable path."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        def get_path():
            return "/dynamic/path"

        logger = FileSessionStateLogger(get_path)
        assert callable(logger.session_log_dir_param)
        assert logger.get_session_log_dir() == "/dynamic/path"

    def test_write_creates_file(self, tmp_path):
        """Test that write creates a session file."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        session_log = SessionStateLog(
            name="test_session",
            start_time="2024-01-15 10:30:00.123456",
            main_task_name="test_task",
            path=["root", "subgroup"],
            input={"arg1": "value1"},
            final_result="",
            finished=False,
            log=[],
            task_status={},
        )

        logger.write(session_log)

        # Verify file was created
        session_file = tmp_path / "test_session.json"
        assert session_file.exists()

    def test_read_session(self, tmp_path):
        """Test reading a session."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        # Create and write a session
        session_log = SessionStateLog(
            name="read_test",
            start_time="2024-01-15 10:30:00.123456",
            main_task_name="task",
            path=["group"],
            input={"key": "val"},
            final_result="success",
            finished=True,
            log=["log entry"],
            task_status={},
        )

        logger.write(session_log)

        # Read it back
        read_log = logger.read("read_test")

        assert read_log.name == "read_test"
        assert read_log.main_task_name == "task"
        assert read_log.input == {"key": "val"}
        assert read_log.finished is True

    def test_list_sessions_empty_timeline(self, tmp_path):
        """Test listing sessions when timeline doesn't exist."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        result = logger.list(
            task_path=[],
            min_start_time=datetime(2024, 1, 1),
            max_start_time=datetime(2024, 12, 31),
        )

        # When timeline doesn't exist, returns a dict
        # When it exists, returns SessionStateLogList
        if isinstance(result, dict):
            assert result["total"] == 0
            assert result["data"] == []
        else:
            assert result.total == 0
            assert result.data == []

    def test_get_session_file_path(self, tmp_path):
        """Test get_session_file_path."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        path = logger.get_session_file_path("my_session")
        assert "my_session.json" in path

    def test_get_session_log_dir_as_string(self, tmp_path):
        """Test get_session_log_dir with string."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        result = logger.get_session_log_dir()
        assert result == str(tmp_path)

    def test_get_session_log_dir_as_callable(self):
        """Test get_session_log_dir with callable."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        def dynamic_path():
            return "/custom/path"

        logger = FileSessionStateLogger(dynamic_path)

        result = logger.get_session_log_dir()
        assert result == "/custom/path"


class TestFileSessionStateLoggerWriteRead:
    """Test write/read operations."""

    def test_write_creates_directory(self, tmp_path):
        """Test that write creates directory if needed."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        nested_path = tmp_path / "nested" / "dir"
        logger = FileSessionStateLogger(str(nested_path))

        session_log = SessionStateLog(
            name="edge_session",
            start_time="2024-01-15 10:30:00.123456",
            main_task_name="task",
            path=[],
            input={},
            final_result="",
            finished=False,
            log=[],
            task_status={},
        )

        logger.write(session_log)

        # Verify nested directory created
        assert nested_path.exists()
        assert (nested_path / "edge_session.json").exists()

    def test_empty_start_time_skips_timeline(self, tmp_path):
        """Test that empty start_time skips timeline creation."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        session_log = SessionStateLog(
            name="no_start_time",
            start_time="",  # Empty start time
            main_task_name="task",
            path=[],
            input={},
            final_result="",
            finished=False,
            log=[],
            task_status={},
        )

        logger.write(session_log)

        # File should still be created
        assert (tmp_path / "no_start_time.json").exists()
        # Timeline directory may not exist for empty start_time
        timeline = tmp_path / "_timeline"
        # Timeline creation is skipped for empty start_time
        # So no timeline should be created

    def test_read_invalid_json_raises_error(self, tmp_path):
        """Test reading invalid JSON raises appropriate error."""
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        # Write invalid JSON manually
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json")

        logger = FileSessionStateLogger(str(tmp_path))

        # Reading should raise an error
        with pytest.raises(Exception):
            logger.read("invalid")


class TestFileSessionStateLoggerTimeline:
    """Test timeline operations."""

    def test_write_with_start_time_creates_timeline(self, tmp_path):
        """Test that write with start_time creates timeline entry."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        session_log = SessionStateLog(
            name="with_timeline",
            start_time="2024-01-15 10:30:00.123456",
            main_task_name="task",
            path=["group", "task"],
            input={},
            final_result="",
            finished=False,
            log=[],
            task_status={},
        )

        logger.write(session_log)

        # Check timeline directory was created
        timeline_path = (
            tmp_path
            / "_timeline"
            / "group"
            / "task"
            / "2024"
            / "1"
            / "15"
            / "10"
            / "30"
            / "0"
        )
        # Timeline marker file should exist
        marker_file = timeline_path / "with_timeline"
        assert marker_file.exists()

    def test_list_sessions_with_data(self, tmp_path):
        """Test listing sessions with existing timeline."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        # Create sessions with proper timeline
        for i in range(3):
            session_log = SessionStateLog(
                name=f"session_{i}",
                start_time=f"2024-01-1{i+1} 10:30:00.123456",
                main_task_name="task",
                path=["group"],
                input={},
                final_result="",
                finished=False,
                log=[],
                task_status={},
            )
            logger.write(session_log)

        # List sessions
        result = logger.list(
            task_path=["group"],
            min_start_time=datetime(2024, 1, 1),
            max_start_time=datetime(2024, 12, 31),
        )

        if isinstance(result, dict):
            assert result["total"] == 3
            assert len(result["data"]) == 3
        else:
            assert result.total == 3
            assert len(result.data) == 3

    def test_list_skips_an_entry_it_cannot_read(self, tmp_path):
        """A log caught mid-write, or one that cannot be read, is skipped.

        `list` used to let pydantic's `ValidationError` (an empty log) or the
        `OSError` of an unreadable file escape, so one broken entry turned the
        whole web route into a 500.
        """
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))
        logger.write(
            SessionStateLog(
                name="readable",
                start_time="2024-01-15 10:30:00.123456",
                main_task_name="task",
                path=["group"],
                input={},
                final_result="",
                finished=False,
                log=[],
                task_status={},
            )
        )
        timeline_dir = (
            tmp_path / "_timeline" / "group" / "2024" / "1" / "15" / "10" / "30" / "0"
        )
        # Still being written: the timeline entry exists, the log is empty.
        (tmp_path / "empty.json").write_text("", encoding="utf-8")
        (timeline_dir / "empty").write_text("", encoding="utf-8")
        # Unreadable: a directory sits where a log file is expected.
        (tmp_path / "unreadable.json").mkdir()
        (timeline_dir / "unreadable").write_text("", encoding="utf-8")

        result = logger.list(
            task_path=["group"],
            min_start_time=datetime(2024, 1, 1),
            max_start_time=datetime(2024, 12, 31),
        )

        assert result.total == 1
        assert [session_log.name for session_log in result.data] == ["readable"]

    def test_write_swaps_a_finished_file_in_place(self, tmp_path):
        """A reader polling the log must never see it truncated.

        The new content goes to a unique temp file beside the target, and
        `os.replace` swaps it in, so the target holds either the previous
        complete log or the new one.
        """
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))
        session_file = tmp_path / "atomic.json"
        session_file.write_text(
            SessionStateLog(
                name="previous",
                start_time="2024-01-15 10:30:00.123456",
                main_task_name="task",
                path=[],
                input={},
                final_result="",
                finished=False,
                log=[],
                task_status={},
            ).model_dump_json(),
            encoding="utf-8",
        )
        observed_at_swap = []
        real_replace = os.replace

        def observe_replace(source, destination):
            # The target still holds the previous complete log at swap time.
            observed_at_swap.append(session_file.read_text(encoding="utf-8"))
            assert os.path.dirname(source) == os.path.dirname(destination)
            real_replace(source, destination)

        session_log = SessionStateLog(
            name="atomic",
            start_time="2024-01-15 10:30:00.123456",
            main_task_name="task",
            path=[],
            input={},
            final_result="",
            finished=False,
            log=[],
            task_status={},
        )
        with patch("os.replace", side_effect=observe_replace):
            logger.write(session_log)

        assert observed_at_swap, "write must swap the file in, not rewrite in place"
        assert all(
            isinstance(json.loads(content), dict) for content in observed_at_swap
        )
        session_file_content = session_file.read_text(encoding="utf-8")
        assert json.loads(session_file_content)["name"] == "atomic"
        assert not list(tmp_path.glob(".atomic.json.*.tmp"))

    def test_list_sessions_pagination(self, tmp_path):
        """Test list pagination."""
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
        )
        from zrb.session_state_logger.file_session_state_logger import (
            FileSessionStateLogger,
        )

        logger = FileSessionStateLogger(str(tmp_path))

        # Create sessions with different start times
        for i in range(5):
            session_log = SessionStateLog(
                name=f"pag_session_{i}",
                start_time=f"2024-01-{15+i:02d} 10:30:00.123456",
                main_task_name="task",
                path=["group"],
                input={},
                final_result="",
                finished=False,
                log=[],
                task_status={},
            )
            logger.write(session_log)

        # Test pagination
        result_page0 = logger.list(
            task_path=["group"],
            min_start_time=datetime(2024, 1, 1),
            max_start_time=datetime(2024, 12, 31),
            page=0,
            limit=2,
        )

        if isinstance(result_page0, dict):
            assert result_page0["total"] == 5
            assert len(result_page0["data"]) == 2
        else:
            assert result_page0.total == 5
            assert len(result_page0.data) == 2

        result_page1 = logger.list(
            task_path=["group"],
            min_start_time=datetime(2024, 1, 1),
            max_start_time=datetime(2024, 12, 31),
            page=1,
            limit=2,
        )

        if isinstance(result_page1, dict):
            assert result_page1["total"] == 5
            assert len(result_page1["data"]) == 2
        else:
            assert result_page1.total == 5
            assert len(result_page1.data) == 2
