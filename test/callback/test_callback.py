"""Tests for Callback class."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.callback.callback import Callback


@pytest.fixture
def mock_task():
    """Create a mock task."""
    task = MagicMock()
    task.async_run = AsyncMock(return_value="task_result")
    return task


@pytest.fixture
def mock_session():
    """Create a mock session."""
    session = MagicMock()
    session.name = "test_session"
    session.shared_ctx.input = {}
    session.shared_ctx.xcom = {}
    session.get_ctx = MagicMock()
    ctx = MagicMock()
    session.get_ctx.return_value = ctx
    return session


@pytest.fixture
def mock_parent_session():
    """Create a mock parent session."""
    parent_session = MagicMock()
    parent_session.shared_ctx.xcom = {}
    return parent_session


def test_callback_init(mock_task):
    """Test Callback initialization."""
    callback = Callback(
        task=mock_task,
        input_mapping={"key": "value"},
        xcom_mapping={"parent_key": "child_key"},
        result_queue="result_q",
        error_queue="error_q",
        session_name_queue="session_q",
    )
    assert callback._task == mock_task
    assert callback._input_mapping == {"key": "value"}
    assert callback._xcom_mapping == {"parent_key": "child_key"}
    assert callback._result_queue == "result_q"
    assert callback._error_queue == "error_q"
    assert callback._session_name_queue == "session_q"


def test_callback_init_defaults(mock_task):
    """Test Callback initialization with default values."""
    callback = Callback(
        task=mock_task,
        input_mapping={"key": "value"},
    )
    assert callback._xcom_mapping is None
    assert callback._result_queue is None
    assert callback._error_queue is None
    assert callback._session_name_queue is None


@pytest.mark.asyncio
async def test_callback_async_run_success(mock_task, mock_session, mock_parent_session):
    """Test Callback.async_run with successful task execution."""
    callback = Callback(
        task=mock_task,
        input_mapping={"input_key": "input_value"},
        render_input_mapping=False,
    )

    with patch(
        "zrb.callback.callback.get_str_dict_attr"
    ) as mock_get_attr:
        mock_get_attr.return_value = {"input_key": "rendered_value"}
        result = await callback.async_run(mock_parent_session, mock_session)

    assert result == "task_result"
    # Check input was set
    assert mock_session.shared_ctx.input["input_key"] == "rendered_value"
    # Check snake_case version was also set
    assert mock_session.shared_ctx.input["input_key"] == "rendered_value"


@pytest.mark.asyncio
async def test_callback_async_run_with_xcom_mapping(
    mock_task, mock_session, mock_parent_session
):
    """Test Callback.async_run with xcom mapping."""
    callback = Callback(
        task=mock_task,
        input_mapping={},
        xcom_mapping={"parent_xcom": "child_xcom"},
    )

    # Set up parent xcom
    mock_parent_session.shared_ctx.xcom["parent_xcom"] = "parent_value"

    with patch(
        "zrb.callback.callback.get_str_dict_attr"
    ) as mock_get_attr:
        mock_get_attr.return_value = {}
        await callback.async_run(mock_parent_session, mock_session)

    # Check xcom was mapped
    assert mock_session.shared_ctx.xcom["child_xcom"] == "parent_value"


@pytest.mark.asyncio
async def test_callback_async_run_publishes_session_name(
    mock_task, mock_session, mock_parent_session
):
    """Test Callback.async_run publishes session name."""
    from zrb.xcom.xcom import Xcom

    callback = Callback(
        task=mock_task,
        input_mapping={},
        session_name_queue="session_names",
    )

    with patch(
        "zrb.callback.callback.get_str_dict_attr"
    ) as mock_get_attr:
        mock_get_attr.return_value = {}
        await callback.async_run(mock_parent_session, mock_session)

    # Check session name was published
    assert "session_names" in mock_parent_session.shared_ctx.xcom
    assert isinstance(mock_parent_session.shared_ctx.xcom["session_names"], Xcom)


@pytest.mark.asyncio
async def test_callback_async_run_publishes_result(
    mock_task, mock_session, mock_parent_session
):
    """Test Callback.async_run publishes result to parent session."""
    from zrb.xcom.xcom import Xcom

    callback = Callback(
        task=mock_task,
        input_mapping={},
        result_queue="results",
    )

    with patch(
        "zrb.callback.callback.get_str_dict_attr"
    ) as mock_get_attr:
        mock_get_attr.return_value = {}
        await callback.async_run(mock_parent_session, mock_session)

    # Check result was published
    assert "results" in mock_parent_session.shared_ctx.xcom
    xcom = mock_parent_session.shared_ctx.xcom["results"]
    assert isinstance(xcom, Xcom)


@pytest.mark.asyncio
async def test_callback_async_run_handles_error(
    mock_task, mock_session, mock_parent_session
):
    """Test Callback.async_run handles errors."""
    from zrb.xcom.xcom import Xcom

    # Make task raise an error
    mock_task.async_run = AsyncMock(side_effect=ValueError("Test error"))

    callback = Callback(
        task=mock_task,
        input_mapping={},
        error_queue="errors",
    )

    with patch(
        "zrb.callback.callback.get_str_dict_attr"
    ) as mock_get_attr:
        mock_get_attr.return_value = {}
        result = await callback.async_run(mock_parent_session, mock_session)

    # Check error was published
    assert "errors" in mock_parent_session.shared_ctx.xcom
    xcom = mock_parent_session.shared_ctx.xcom["errors"]
    assert isinstance(xcom, Xcom)
    # Result should be None when error occurs
    assert result is None


def test_maybe_publish_to_parent_session_none_queue(mock_parent_session):
    """Test _maybe_publish_to_parent_session with None queue."""
    callback = Callback(task=MagicMock(), input_mapping={})
    # Should not raise and should not modify parent
    callback._maybe_publish_to_parent_session(
        parent_session=mock_parent_session,
        xcom_name=None,
        value="test_value",
    )
    assert mock_parent_session.shared_ctx.xcom == {}


def test_maybe_publish_to_parent_session_new_xcom(mock_parent_session):
    """Test _maybe_publish_to_parent_session creates new Xcom if needed."""
    from zrb.xcom.xcom import Xcom

    callback = Callback(task=MagicMock(), input_mapping={})
    callback._maybe_publish_to_parent_session(
        parent_session=mock_parent_session,
        xcom_name="new_queue",
        value="test_value",
    )

    assert "new_queue" in mock_parent_session.shared_ctx.xcom
    assert isinstance(mock_parent_session.shared_ctx.xcom["new_queue"], Xcom)


def test_maybe_publish_to_parent_session_existing_xcom(mock_parent_session):
    """Test _maybe_publish_to_parent_session uses existing Xcom."""
    from zrb.xcom.xcom import Xcom

    # Pre-create an Xcom
    existing_xcom = Xcom(["existing_value"])
    mock_parent_session.shared_ctx.xcom["existing_queue"] = existing_xcom

    callback = Callback(task=MagicMock(), input_mapping={})
    callback._maybe_publish_to_parent_session(
        parent_session=mock_parent_session,
        xcom_name="existing_queue",
        value="new_value",
    )

    # Should have pushed to existing Xcom
    assert mock_parent_session.shared_ctx.xcom["existing_queue"] is existing_xcom