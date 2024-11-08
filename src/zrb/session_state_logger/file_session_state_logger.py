import datetime
import json
import os

from ..session_state_log.session_state_log import SessionStateLog, SessionStateLogs
from .any_session_state_logger import AnySessionStateLogger


class FileSessionStateLogger(AnySessionStateLogger):

    def __init__(self, session_log_dir: str):
        self._session_log_dir = session_log_dir

    def write(self, session_log: SessionStateLog):
        session_file_path = self._get_session_file_path(session_log["name"])
        with open(session_file_path, "w") as f:
            f.write(json.dumps(session_log))
        start_time = self._get_start_time(session_log)
        if start_time is None:
            return
        timeline_dir_path = self._get_timeline_dir_path(session_log, start_time)
        os.makedirs(timeline_dir_path, exist_ok=True)
        with open(os.path.join(timeline_dir_path, session_log["name"]), "w"):
            pass

    def read(self, session_name: str) -> SessionStateLog:
        session_file_path = self._get_session_file_path(session_name)
        with open(session_file_path, "r") as f:
            return json.loads(f.read())

    def list(
        self,
        task_path: list[str],
        min_start_time: datetime.datetime,
        max_start_time: datetime.datetime,
        page: int = 0,
        limit: int = 10,
    ) -> SessionStateLogs:
        matching_sessions = []
        # Traverse the timeline directory and filter sessions
        timeline_dir = os.path.join(self._session_log_dir, "_timeline", *task_path)
        if not os.path.exists(timeline_dir):
            return {"total": 0, "data": []}
        for root, _, files in os.walk(timeline_dir):
            for file_name in files:
                session_name = os.path.splitext(file_name)[0]
                # Read the session and retrieve start time
                session_log = self.read(session_name)
                start_time = self._get_start_time(session_log)
                # Filter sessions based on start time
                if start_time and min_start_time <= start_time <= max_start_time:
                    matching_sessions.append((start_time, session_log))
        # Sort sessions by start time, descending
        matching_sessions.sort(key=lambda x: x[0], reverse=True)
        total = len(matching_sessions)
        # Apply pagination
        start_index = page * limit
        end_index = start_index + limit
        paginated_sessions = matching_sessions[start_index:end_index]
        # Extract session logs from the sorted list of tuples
        data = [session_log for _, session_log in paginated_sessions]
        return {"total": total, "data": data}

    def _get_session_file_path(self, session_name: str) -> str:
        return os.path.join(self._session_log_dir, f"{session_name}.json")

    def _get_timeline_dir_path(
        self, session_log: SessionStateLog, start_time: datetime.datetime
    ) -> str:
        year = start_time.year
        month = start_time.month
        day = start_time.day
        hour = start_time.hour
        minute = start_time.minute
        second = start_time.second
        paths = session_log["path"] + [
            f"{year}",
            f"{month}",
            f"{day}",
            f"{hour}",
            f"{minute}",
            f"{second}",
        ]
        return os.path.join(self._session_log_dir, "_timeline", *paths)

    def _get_start_time(self, session_log: SessionStateLog) -> datetime.datetime:
        result: datetime.datetime | None = None
        for task_status in session_log["task_status"].values():
            histories = task_status["history"]
            if len(histories) == 0:
                continue
            first_history = histories[0]
            first_time = datetime.datetime.strptime(
                first_history["time"], "%Y-%m-%d %H:%M:%S.%f"
            )
            if result is None or first_time < result:
                result = first_time
        return result
