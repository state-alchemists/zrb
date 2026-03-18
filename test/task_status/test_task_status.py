"""Tests for task_status.py - Task status tracking."""

import datetime

import pytest


class TestTaskStatusConstants:
    """Test task status constants."""

    def test_status_constants_exist(self):
        """Test that all status constants are defined."""
        from zrb.task_status.task_status import (
            TASK_STARTED,
            TASK_READY,
            TASK_COMPLETED,
            TASK_SKIPPED,
            TASK_FAILED,
            TASK_PERMANENTLY_FAILED,
            TASK_TERMINATED,
            TASK_RESET,
        )

        assert TASK_STARTED == "started"
        assert TASK_READY == "ready"
        assert TASK_COMPLETED == "completed"
        assert TASK_SKIPPED == "skipped"
        assert TASK_FAILED == "failed"
        assert TASK_PERMANENTLY_FAILED == "permanently-failed"
        assert TASK_TERMINATED == "terminated"
        assert TASK_RESET == "reset"


class TestTaskStatusInit:
    """Test TaskStatus initialization."""

    def test_init_default_values(self):
        """Test TaskStatus initializes with default values."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        assert status.is_started is False
        assert status.is_ready is False
        assert status.is_completed is False
        assert status.is_skipped is False
        assert status.is_failed is False
        assert status.is_permanently_failed is False
        assert status.is_terminated is False
        assert status.history == []

    def test_repr(self):
        """Test TaskStatus string representation."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        assert repr(status) == "<TaskStatus []>"

        status.mark_as_started()
        assert "started" in repr(status)


class TestTaskStatusMarking:
    """Test TaskStatus marking methods."""

    def test_mark_as_started(self):
        """Test marking task as started."""
        from zrb.task_status.task_status import TaskStatus, TASK_STARTED

        status = TaskStatus()
        status.mark_as_started()

        assert status.is_started is True
        assert status.history[0][0] == TASK_STARTED
        assert isinstance(status.history[0][1], datetime.datetime)

    def test_mark_as_started_clears_failed(self):
        """Test that mark_as_started clears failed status."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status._is_failed = True
        status.mark_as_started()

        assert status.is_failed is False

    def test_mark_as_failed(self):
        """Test marking task as failed."""
        from zrb.task_status.task_status import TaskStatus, TASK_FAILED

        status = TaskStatus()
        status.mark_as_failed()

        assert status.is_failed is True
        assert status.history[0][0] == TASK_FAILED

    def test_mark_as_ready(self):
        """Test marking task as ready."""
        from zrb.task_status.task_status import TaskStatus, TASK_READY

        status = TaskStatus()
        status.mark_as_ready()

        assert status.is_ready is True
        assert status.history[0][0] == TASK_READY

    def test_mark_as_completed(self):
        """Test marking task as completed."""
        from zrb.task_status.task_status import TaskStatus, TASK_COMPLETED

        status = TaskStatus()
        status.mark_as_completed()

        assert status.is_completed is True
        assert status.history[0][0] == TASK_COMPLETED

    def test_mark_as_skipped(self):
        """Test marking task as skipped."""
        from zrb.task_status.task_status import TaskStatus, TASK_SKIPPED

        status = TaskStatus()
        status.mark_as_skipped()

        assert status.is_skipped is True
        assert status.history[0][0] == TASK_SKIPPED

    def test_mark_as_permanently_failed(self):
        """Test marking task as permanently failed."""
        from zrb.task_status.task_status import TaskStatus, TASK_PERMANENTLY_FAILED

        status = TaskStatus()
        status.mark_as_permanently_failed()

        assert status.is_permanently_failed is True
        assert status.history[0][0] == TASK_PERMANENTLY_FAILED

    def test_mark_as_terminated(self):
        """Test marking task as terminated."""
        from zrb.task_status.task_status import TaskStatus, TASK_TERMINATED

        status = TaskStatus()
        status.mark_as_terminated()

        assert status.is_terminated is True
        assert status.history[0][0] == TASK_TERMINATED

    def test_mark_as_terminated_idempotent(self):
        """Test that mark_as_terminated is idempotent."""
        from zrb.task_status.task_status import TaskStatus, TASK_TERMINATED

        status = TaskStatus()
        status.mark_as_terminated()
        status.mark_as_terminated()

        assert status.is_terminated is True
        # Should only have one TERMINATED entry
        terminated_count = sum(1 for h in status.history if h[0] == TASK_TERMINATED)
        assert terminated_count == 1


class TestTaskStatusTerminatedEdgeCases:
    """Test TaskStatus terminated edge cases."""

    def test_terminated_when_skipped_no_history_entry(self):
        """Test terminated doesn't add history when skipped."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_skipped()
        status.mark_as_terminated()

        assert status.is_terminated is True
        assert len(status.history) == 1  # Only skipped

    def test_terminated_when_completed_no_history_entry(self):
        """Test terminated doesn't add history when completed."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_completed()
        status.mark_as_terminated()

        assert status.is_terminated is True
        assert len(status.history) == 1  # Only completed

    def test_terminated_when_permanently_failed_no_history_entry(self):
        """Test terminated doesn't add history when permanently failed."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_permanently_failed()
        status.mark_as_terminated()

        assert status.is_terminated is True
        assert len(status.history) == 1  # Only permanently failed


class TestTaskStatusReset:
    """Test TaskStatus reset methods."""

    def test_reset(self):
        """Test reset method."""
        from zrb.task_status.task_status import TaskStatus, TASK_RESET

        status = TaskStatus()
        status.mark_as_started()
        status.reset()

        assert status.is_started is False
        assert status.is_ready is False
        assert status.is_completed is False
        assert status.is_skipped is False
        assert status.is_failed is False
        assert status.is_permanently_failed is False
        assert status.history[-1][0] == TASK_RESET

    def test_reset_history(self):
        """Test reset_history method."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_started()
        status.mark_as_completed()
        status.reset_history()

        assert status.history == []


class TestTaskStatusAllowRunDownstream:
    """Test allow_run_downstream property."""

    def test_allow_run_downstream_when_ready(self):
        """Test allow_run_downstream when ready."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_ready()

        assert status.allow_run_downstream is True

    def test_allow_run_downstream_when_skipped(self):
        """Test allow_run_downstream when skipped."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_skipped()

        assert status.allow_run_downstream is True

    def test_allow_run_downstream_when_failed(self):
        """Test allow_run_downstream when failed."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_failed()

        assert status.allow_run_downstream is False

    def test_allow_run_downstream_when_permanently_failed(self):
        """Test allow_run_downstream when permanently failed."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_permanently_failed()

        assert status.allow_run_downstream is False

    def test_allow_run_downstream_when_terminated(self):
        """Test allow_run_downstream when terminated."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_terminated()

        assert status.allow_run_downstream is False

    def test_allow_run_downstream_when_started(self):
        """Test allow_run_downstream when started but not ready."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        status.mark_as_started()

        assert status.allow_run_downstream is False

    def test_allow_run_downstream_initial_state(self):
        """Test allow_run_downstream in initial state."""
        from zrb.task_status.task_status import TaskStatus

        status = TaskStatus()
        assert status.allow_run_downstream is False