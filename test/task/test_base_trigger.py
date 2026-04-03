"""Tests for BaseTrigger class."""

import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest

from zrb.callback.any_callback import AnyCallback
from zrb.context.shared_context import SharedContext
from zrb.dot_dict.dot_dict import DotDict
from zrb.session.session import Session
from zrb.task.base_task import BaseTask
from zrb.task.base_trigger import BaseTrigger
from zrb.xcom.xcom import Xcom


class MockCallback(AnyCallback):
    """Mock callback for testing."""

    async def async_run(self, parent_session, session):
        return "callback_result"


def get_mock_session():
    """Create a mock session with shared context for testing."""
    shared_ctx = SharedContext(
        input={},
        args=[],
        env={},
        xcom={},
    )

    session = MagicMock(spec=Session)
    session.shared_ctx = shared_ctx
    session.defer_coro = Mock()
    session.root_group = MagicMock()

    return session


class TestBaseTriggerProperties:
    """Test BaseTrigger property methods."""

    def test_queue_name_default(self):
        """Test queue_name defaults to task name."""
        trigger = BaseTrigger(name="test_trigger")
        assert trigger.queue_name == "test_trigger"

    def test_queue_name_custom(self):
        """Test queue_name with custom value."""
        trigger = BaseTrigger(name="test_trigger", queue_name="custom_queue")
        assert trigger.queue_name == "custom_queue"

    def test_readiness_checks_default(self):
        """Test readiness_checks returns default BaseTask when none provided."""
        trigger = BaseTrigger(name="test_trigger")
        checks = trigger.readiness_checks
        assert len(checks) == 1
        assert isinstance(checks[0], BaseTask)
        assert checks[0].name == "test_trigger-check"

    def test_readiness_checks_with_provided(self):
        """Test readiness_checks returns provided checks."""
        check_task = BaseTask(name="check_task")
        trigger = BaseTrigger(name="test_trigger", readiness_check=check_task)
        checks = trigger.readiness_checks
        assert checks == [check_task]

    def test_callbacks_single(self):
        """Test callbacks property with single callback."""
        callback = MockCallback()
        trigger = BaseTrigger(name="test_trigger", callback=callback)
        assert trigger.callbacks == [callback]

    def test_callbacks_list(self):
        """Test callbacks property with list of callbacks."""
        callback1 = MockCallback()
        callback2 = MockCallback()
        trigger = BaseTrigger(name="test_trigger", callback=[callback1, callback2])
        assert trigger.callbacks == [callback1, callback2]

    def test_callbacks_empty(self):
        """Test callbacks property with no callbacks."""
        trigger = BaseTrigger(name="test_trigger")
        assert trigger.callbacks == []


class TestBaseTriggerXCom:
    """Test BaseTrigger XCom methods."""

    def test_get_exchange_xcom_creates_new(self):
        """Test _get_exchange_xcom creates XCom if not exists."""
        trigger = BaseTrigger(name="test_trigger", queue_name="my_queue")
        session = get_mock_session()

        xcom = trigger._get_exchange_xcom(session)
        assert isinstance(xcom, Xcom)
        assert "my_queue" in session.shared_ctx.xcom

    def test_get_exchange_xcom_returns_existing(self):
        """Test _get_exchange_xcom returns existing XCom."""
        trigger = BaseTrigger(name="test_trigger", queue_name="my_queue")
        session = get_mock_session()
        existing_xcom = Xcom()
        existing_xcom.push("existing_data")
        session.shared_ctx._xcom["my_queue"] = existing_xcom

        xcom = trigger._get_exchange_xcom(session)
        assert xcom is existing_xcom

    def test_push_exchange_xcom(self):
        """Test push_exchange_xcom pushes data to XCom."""
        trigger = BaseTrigger(name="test_trigger", queue_name="my_queue")
        session = get_mock_session()

        trigger.push_exchange_xcom(session, "test_data")

        xcom = session.shared_ctx.xcom["my_queue"]
        data = xcom.pop()
        assert data == "test_data"

    def test_pop_exchange_xcom(self):
        """Test pop_exchange_xcom pops data from XCom."""
        trigger = BaseTrigger(name="test_trigger", queue_name="my_queue")
        session = get_mock_session()
        session.shared_ctx._xcom["my_queue"] = Xcom()
        session.shared_ctx._xcom["my_queue"].push("data_to_pop")

        data = trigger.pop_exchange_xcom(session)
        assert data == "data_to_pop"

    def test_push_and_pop_exchange_xcom(self):
        """Test push and pop work together."""
        trigger = BaseTrigger(name="test_trigger", queue_name="test_queue")
        session = get_mock_session()

        # Push multiple items
        trigger.push_exchange_xcom(session, "first")
        trigger.push_exchange_xcom(session, "second")

        # Pop should return in FIFO order (XCom is a queue)
        assert trigger.pop_exchange_xcom(session) == "first"
        assert trigger.pop_exchange_xcom(session) == "second"

    def test_get_exchange_xcom_with_named_queue(self):
        """Test _get_exchange_xcom with custom queue name."""
        trigger = BaseTrigger(name="test_trigger", queue_name="custom_queue")
        session = get_mock_session()

        xcom = trigger._get_exchange_xcom(session)
        assert isinstance(xcom, Xcom)
        assert "custom_queue" in session.shared_ctx.xcom
