import logging

import pytest

pytest.importorskip("loguru", reason="loguru ships with pipecat, the voice extra")

from loguru import logger  # noqa: E402

from zrb.llm.voice.manager import route_pipecat_logs  # noqa: E402


def test_pipecat_logs_go_through_logging_not_straight_to_the_terminal(caplog, capfd):
    route_pipecat_logs()

    with caplog.at_level(logging.WARNING):
        logger.debug("Loading Pocket TTS model")
        logger.warning("the service is slow")

    assert "Loading Pocket TTS model" not in capfd.readouterr().err
    assert [r.getMessage() for r in caplog.records] == ["the service is slow"]
