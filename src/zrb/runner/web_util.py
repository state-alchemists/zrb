import asyncio
import json
import os
import sys

from ..session.any_session import AnySession
from ..task.any_task import AnyTask


class SessionSnapshotCondition:
    def __init__(self):
        self._should_stop = False

    @property
    def should_stop(self) -> bool:
        return self._should_stop

    def stop(self):
        self._should_stop = True


def start_event_loop(event_loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()


async def run_task_and_snapshot_session(
    session: AnySession, session_dir: str, task: AnyTask, str_kwargs: dict[str, str]
):
    snapshot_condition = SessionSnapshotCondition()
    run_task = asyncio.create_task(task.async_run(session, str_kwargs))
    snapshot_session_periodically = asyncio.create_task(
        _snapshot_session_periodically(session, session_dir, snapshot_condition)
    )
    await run_task
    snapshot_condition.stop()
    await snapshot_session_periodically
    print(session_to_log_dict(session), file=sys.stderr)


def get_session_log_dict(session_dir: str, session_name: str):
    session_file_name = _get_session_log_file_name(session_dir, session_name)
    with open(session_file_name, "r") as f:
        return json.loads(f.read())


async def _snapshot_session_periodically(
    session: AnySession, session_dir: str, snapshot_condition: SessionSnapshotCondition
):
    while True:
        _save_session_log_as_json(session, session_dir)
        if snapshot_condition.should_stop:
            _save_session_log_as_json(session, session_dir, finished=True)
            break
        await asyncio.sleep(0.1)


def _save_session_log_as_json(
    session: AnySession, session_dir: str, finished: bool = False
):
    session_file_name = _get_session_log_file_name(session_dir, session.name)
    session_dict = session_to_log_dict(session)
    session_dict["finished"] = finished
    os.makedirs(session_dir, exist_ok=True)
    with open(session_file_name, "w") as f:
        f.write(json.dumps(session_dict))


def _get_session_log_file_name(session_dir: str, session_name: str):
    return os.path.join(session_dir, f"session-{session_name}.json")


def session_to_log_dict(session: AnySession) -> str:
    task_status_dict = {}
    for task, task_status in session.status.items():
        task_status_dict[task.name] = {
            "history": [
                (status, time.strftime("%Y-%m-%d %H:%M:%S.%f"))
                for status, time in task_status.history
            ],
            "is_started": task_status.is_started,
            "is_ready": task_status.is_ready,
            "is_completed": task_status.is_completed,
            "is_skipped": task_status.is_skipped,
            "is_failed": task_status.is_failed,
            "is_permanently_failed": task_status.is_permanently_failed,
        }
    return {
        "name": session.name,
        "final_result": f"{session.shared_ctx.final_result}",
        "log": session.shared_ctx.shared_log,
        "task_status": task_status_dict,
        "input": session.shared_ctx.input,
    }
