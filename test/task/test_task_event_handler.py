from zrb.helper.typing import List
from zrb.task.decorator import python_task
from zrb.task.any_task import AnyTask


def create_on_triggered(logs: List[str]):
    def on_triggered(task: AnyTask):
        logs.append('triggered')
    return on_triggered


def create_on_waiting(logs: List[str]):
    def on_waiting(task: AnyTask):
        logs.append('waiting')
    return on_waiting


def create_on_skipped(logs: List[str]):
    def on_skipped(task: AnyTask):
        logs.append('skipped')
    return on_skipped


def create_on_started(logs: List[str]):
    def on_started(task: AnyTask):
        logs.append('started')
    return on_started


def create_on_ready(logs: List[str]):
    def on_ready(task: AnyTask):
        logs.append('ready')
    return on_ready


def create_on_retry(logs: List[str]):
    def on_retry(task: AnyTask):
        logs.append('retry')
    return on_retry


def create_on_failed(logs: List[str]):
    def on_failed(task: AnyTask, is_last_attempt: bool, exception: Exception):
        if is_last_attempt:
            logs.append('failed for good')
            return
        logs.append('failed')
    return on_failed


def test_success_task():
    logs = []

    @python_task(
        name='task',
        on_triggered=create_on_triggered(logs),
        on_waiting=create_on_waiting(logs),
        on_skipped=create_on_skipped(logs),
        on_started=create_on_started(logs),
        on_ready=create_on_ready(logs),
        on_retry=create_on_retry(logs),
        on_failed=create_on_failed(logs)
    )
    def task(*args, **kwargs) -> str:
        return 'ok'

    function = task.to_function()
    function()
    assert len(logs) == 4
    assert logs[0] == 'triggered'
    assert logs[1] == 'waiting'
    assert logs[2] == 'started'
    assert logs[3] == 'ready'


def test_skipped_task():
    logs = []

    @python_task(
        name='task',
        should_execute=False,
        on_triggered=create_on_triggered(logs),
        on_waiting=create_on_waiting(logs),
        on_skipped=create_on_skipped(logs),
        on_started=create_on_started(logs),
        on_ready=create_on_ready(logs),
        on_retry=create_on_retry(logs),
        on_failed=create_on_failed(logs)
    )
    def task(*args, **kwargs) -> str:
        return 'ok'

    function = task.to_function()
    function()
    assert len(logs) == 4
    assert logs[0] == 'triggered'
    assert logs[1] == 'waiting'
    assert logs[2] == 'skipped'
    assert logs[3] == 'ready'


def test_failed_for_good_task():
    logs = []

    @python_task(
        name='task',
        retry=2,
        on_triggered=create_on_triggered(logs),
        on_waiting=create_on_waiting(logs),
        on_skipped=create_on_skipped(logs),
        on_started=create_on_started(logs),
        on_ready=create_on_ready(logs),
        on_retry=create_on_retry(logs),
        on_failed=create_on_failed(logs)
    )
    def task(*args, **kwargs) -> str:
        raise Exception('error')

    function = task.to_function()
    is_error = False
    try:
        function()
    except Exception:
        is_error = True
    assert is_error
    assert len(logs) == 10
    assert logs[0] == 'triggered'
    assert logs[1] == 'waiting'
    assert logs[2] == 'started'
    assert logs[3] == 'failed'
    assert logs[4] == 'retry'
    assert logs[5] == 'started'
    assert logs[6] == 'failed'
    assert logs[7] == 'retry'
    assert logs[8] == 'started'
    assert logs[9] == 'failed for good'


def test_failed_then_success_task():
    logs = []
    state = {'retry': 0}

    @python_task(
        name='task',
        on_triggered=create_on_triggered(logs),
        on_waiting=create_on_waiting(logs),
        on_skipped=create_on_skipped(logs),
        on_started=create_on_started(logs),
        on_ready=create_on_ready(logs),
        on_retry=create_on_retry(logs),
        on_failed=create_on_failed(logs)
    )
    def task(*args, **kwargs) -> str:
        state['retry'] += 1
        if state['retry'] == 3:
            return 'ok'
        raise Exception('Try again')

    function = task.to_function()
    function()
    assert len(logs) == 10
    assert logs[0] == 'triggered'
    assert logs[1] == 'waiting'
    assert logs[2] == 'started'
    assert logs[3] == 'failed'
    assert logs[4] == 'retry'
    assert logs[5] == 'started'
    assert logs[6] == 'failed'
    assert logs[7] == 'retry'
    assert logs[8] == 'started'
    assert logs[9] == 'ready'
