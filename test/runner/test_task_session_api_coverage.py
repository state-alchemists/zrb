import pytest
from unittest.mock import MagicMock
from zrb.runner.web_route.task_session_api_route import sanitize_session_state_log, sanitize_session_state_log_list
from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.task.any_task import AnyTask
from zrb.input.base_input import BaseInput

def test_sanitize_session_state_log():
    task = MagicMock(spec=AnyTask)
    task.inputs = [BaseInput(name="real-input", description="")]
    
    log = MagicMock(spec=SessionStateLog)
    log.input = {"real-input": "val", "snake_alias": "val"}
    log.name = "session"
    log.start_time = "2026-01-01"
    log.main_task_name = "task"
    log.path = ["root", "task"]
    log.final_result = "ok"
    log.finished = True
    log.log = ["line1"]
    log.task_status = {}
    
    sanitized = sanitize_session_state_log(task, log)
    assert sanitized.input == {"real-input": "val"}
    assert "snake_alias" not in sanitized.input

def test_sanitize_session_state_log_list():
    task = MagicMock(spec=AnyTask)
    task.inputs = [BaseInput(name="i1", description="")]
    
    log = MagicMock(spec=SessionStateLog)
    log.input = {"i1": "v1", "alias": "v1"}
    log.name = "s1"
    log.start_time = "2026-01-01"
    log.main_task_name = "task"
    log.path = ["p"]
    log.final_result = ""
    log.finished = True
    log.log = []
    log.task_status = {}
    
    log_list = SessionStateLogList(total=1, data=[log])
    
    sanitized_list = sanitize_session_state_log_list(task, log_list)
    assert sanitized_list.total == 1
    assert sanitized_list.data[0].input == {"i1": "v1"}
