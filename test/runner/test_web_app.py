import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.group import Group
from zrb.runner.web_app import (
    CancelledErrorFilter,
    cancel_task_runs,
    configure_uvicorn_logging,
    create_web_app,
)
from zrb.session_state_logger.session_state_logger_factory import session_state_logger


class TestCancelledErrorFilter:
    def test_filter_allows_normal_messages(self):
        filter_obj = CancelledErrorFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Normal message",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(record) is True

    def test_filter_allows_non_cancellation_errors(self):
        filter_obj = CancelledErrorFilter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error message",
                args=(),
                exc_info=exc_info,
            )
            assert filter_obj.filter(record) is True

    def test_filter_blocks_cancelled_error(self):
        filter_obj = CancelledErrorFilter()
        try:
            raise asyncio.CancelledError()
        except asyncio.CancelledError:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Cancelled",
                args=(),
                exc_info=exc_info,
            )
            assert filter_obj.filter(record) is False

    def test_filter_blocks_cancel_task_message(self):
        filter_obj = CancelledErrorFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Cancel 2 running task(s), timeout graceful shutdown exceeded",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(record) is False

    def test_filter_allows_other_error_messages(self):
        filter_obj = CancelledErrorFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Some other error message",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(record) is True


class TestConfigureUvicornLogging:
    def test_configure_uvicorn_logging(self):
        configure_uvicorn_logging()
        for logger_name in [
            "uvicorn",
            "uvicorn.error",
            "uvicorn.protocols.http.httptools_impl",
            "uvicorn.protocols.http.h11_impl",
        ]:
            logger = logging.getLogger(logger_name)
            has_filter = any(
                isinstance(f, CancelledErrorFilter) for f in logger.filters
            )
            assert has_filter, f"Logger {logger_name} should have CancelledErrorFilter"

    def test_configure_does_not_duplicate_filters(self):
        configure_uvicorn_logging()
        configure_uvicorn_logging()
        logger = logging.getLogger("uvicorn.error")
        filter_count = sum(
            1 for f in logger.filters if isinstance(f, CancelledErrorFilter)
        )
        assert filter_count == 1, "Filter should only be added once"


class TestCancelTaskRuns:
    @pytest.mark.asyncio
    async def test_a_task_run_ignoring_the_first_cancel_does_not_stop_shutdown(
        self, caplog
    ):
        """Swallowing one cancellation is survivable; the run is named and left."""
        release = asyncio.Event()

        async def ignore_the_first_cancel():
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()

        task_run = asyncio.create_task(ignore_the_first_cancel())
        await asyncio.sleep(0)
        try:
            with caplog.at_level(logging.WARNING):
                await cancel_task_runs([task_run], 0.01)
            assert not task_run.done()
        finally:
            release.set()
            await asyncio.gather(task_run, return_exceptions=True)

        assert "Continuing with chat session cleanup" in caplog.text

    @pytest.mark.asyncio
    async def test_a_task_run_refusing_every_cancel_does_not_stop_shutdown(
        self, caplog
    ):
        """`wait_for(gather(...))` waits for the cancellation it asked for.

        A run that catches `CancelledError` again and again never lets the
        gather settle, so `wait_for`'s timeout fires and then the shutdown
        blocks anyway. The survivor is reported by name and left behind.
        """
        release = asyncio.Event()

        async def refuse_every_cancel():
            while not release.is_set():
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    continue

        task_run = asyncio.create_task(refuse_every_cancel(), name="chat-task-run")
        await asyncio.sleep(0)
        try:
            with caplog.at_level(logging.WARNING):
                await cancel_task_runs([task_run], 0.01)
            assert not task_run.done()
        finally:
            release.set()
            await asyncio.gather(task_run, return_exceptions=True)

        assert "chat-task-run" in caplog.text
        assert "Continuing with chat session cleanup" in caplog.text

    @pytest.mark.asyncio
    async def test_no_task_run_returns_at_once(self):
        # Nothing to cancel is the common case: shutdown must not wait it out.
        await cancel_task_runs([], 10)


class TestWebLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_cancels_chat_sessions_after_the_shutdown_wait(
        self, monkeypatch
    ):
        """A shutdown that timed out outlives the coros, not the chat cleanup."""
        import zrb.runner.web_app as web_app_module

        app = create_web_app(
            Group(name="root"),
            WebAuthConfig(
                secret_key="zrb",
                access_token_expire_minutes=30,
                refresh_token_expire_minutes=30,
                access_token_cookie_name="access_token",
                refresh_token_cookie_name="refresh_token",
                enable_auth=False,
                super_admin_username="admin",
                super_admin_password="admin",
                guest_username="guest",
            ),
            session_state_logger,
        )
        session_manager = MagicMock()
        session_manager.cancel_all_sessions = AsyncMock()
        monkeypatch.setattr(
            web_app_module, "should_skip_session_cleanup", lambda: False
        )
        monkeypatch.setattr(
            web_app_module.ChatSessionManager,
            "get_instance_sync",
            lambda: session_manager,
        )

        async with app.router.lifespan_context(app):
            pass

        session_manager.cancel_all_sessions.assert_awaited_once()
