import asyncio
import logging

from zrb.runner.web_app import CancelledErrorFilter, configure_uvicorn_logging


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
