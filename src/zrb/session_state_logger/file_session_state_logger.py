import datetime
import os

from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.util.file import read_file, write_file


class FileSessionStateLogger(AnySessionStateLogger):
    def __init__(self, session_log_dir: str):
        self._session_log_dir = session_log_dir

    def write(self, session_log: SessionStateLog):
        session_file_path = self._get_session_file_path(session_log.name)
        session_dir_path = os.path.dirname(session_file_path)
        if not os.path.isdir(session_dir_path):
            os.makedirs(session_dir_path, exist_ok=True)
        write_file(session_file_path, session_log.model_dump_json())
        start_time = session_log.start_time
        if start_time == "":
            return
        timeline_dir_path = self._get_timeline_dir_path(session_log)
        write_file(os.path.join(timeline_dir_path, session_log.name), "")

    def read(self, session_name: str) -> SessionStateLog:
        session_file_path = self._get_session_file_path(session_name)
        return SessionStateLog.model_validate_json(read_file(session_file_path))

    def list(
        self,
        task_path: list[str],
        min_start_time: datetime.datetime,
        max_start_time: datetime.datetime,
        page: int = 0,
        limit: int = 10,
    ) -> SessionStateLogList:
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
        return SessionStateLogList(total=total, data=data)

    def _get_session_file_path(self, session_name: str) -> str:
        return os.path.join(self._session_log_dir, f"{session_name}.json")

    def _get_timeline_dir_path(self, session_log: SessionStateLog) -> str:
        start_time = self._get_start_time(session_log)
        year = start_time.year
        month = start_time.month
        day = start_time.day
        hour = start_time.hour
        minute = start_time.minute
        second = start_time.second
        paths = session_log.path + [
            f"{year}",
            f"{month}",
            f"{day}",
            f"{hour}",
            f"{minute}",
            f"{second}",
        ]
        return os.path.join(self._session_log_dir, "_timeline", *paths)

    def _get_start_time(self, session_log: SessionStateLog) -> datetime.datetime:
        return datetime.datetime.strptime(
            session_log.start_time, "%Y-%m-%d %H:%M:%S.%f"
        )
