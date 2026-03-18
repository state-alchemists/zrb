"""Tests for Callback class focusing on Public API and behavior."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from zrb.callback.callback import Callback
from zrb.xcom.xcom import Xcom

@pytest.fixture
def mock_task():
    task = MagicMock()
    task.async_run = AsyncMock(return_value="task_result")
    return task

@pytest.fixture
def mock_session():
    session = MagicMock()
    session.name = "test_session"
    session.shared_ctx.input = {}
    session.shared_ctx.xcom = {}
    session.get_ctx = MagicMock()
    session.get_ctx.return_value = MagicMock()
    return session

@pytest.fixture
def mock_parent_session():
    parent_session = MagicMock()
    parent_session.shared_ctx.xcom = {}
    return parent_session

class TestCallbackBehavior:
    """Test Callback using only public methods and verifying behavior."""

    @pytest.mark.asyncio
    async def test_callback_executes_task_and_maps_input(self, mock_task, mock_session, mock_parent_session):
        # Arrange
        callback = Callback(
            task=mock_task,
            input_mapping={"key": "value"},
            render_input_mapping=False,
        )

        # Act
        result = await callback.async_run(mock_parent_session, mock_session)

        # Assert
        assert result == "task_result"
        mock_task.async_run.assert_called_once_with(mock_session)
        assert mock_session.shared_ctx.input["key"] == "value"

    @pytest.mark.asyncio
    async def test_callback_publishes_to_parent_queues(self, mock_task, mock_session, mock_parent_session):
        # Arrange
        callback = Callback(
            task=mock_task,
            input_mapping={},
            result_queue="results",
            session_name_queue="sessions"
        )

        # Act
        await callback.async_run(mock_parent_session, mock_session)

        # Assert
        # Verify result was pushed to parent XCom
        assert "results" in mock_parent_session.shared_ctx.xcom
        assert mock_parent_session.shared_ctx.xcom["results"].pop() == "task_result"
        
        # Verify session name was pushed to parent XCom
        assert "sessions" in mock_parent_session.shared_ctx.xcom
        assert mock_parent_session.shared_ctx.xcom["sessions"].pop() == "test_session"

    @pytest.mark.asyncio
    async def test_callback_handles_task_error(self, mock_task, mock_session, mock_parent_session):
        # Arrange
        mock_task.async_run.side_effect = ValueError("Task Failed")
        callback = Callback(
            task=mock_task,
            input_mapping={},
            error_queue="errors"
        )

        # Act
        result = await callback.async_run(mock_parent_session, mock_session)

        # Assert
        assert result is None
        assert "errors" in mock_parent_session.shared_ctx.xcom
        error = mock_parent_session.shared_ctx.xcom["errors"].pop()
        assert isinstance(error, ValueError)
        assert str(error) == "Task Failed"

    @pytest.mark.asyncio
    async def test_callback_maps_xcom_from_parent(self, mock_task, mock_session, mock_parent_session):
        # Arrange
        mock_parent_session.shared_ctx.xcom["parent_data"] = "secret_data"
        callback = Callback(
            task=mock_task,
            input_mapping={},
            xcom_mapping={"parent_data": "child_data"}
        )

        # Act
        await callback.async_run(mock_parent_session, mock_session)

        # Assert
        assert mock_session.shared_ctx.xcom["child_data"] == "secret_data"
