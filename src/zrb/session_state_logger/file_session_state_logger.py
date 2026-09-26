import datetime
import os
import time
from typing import TYPE_CHECKING, Callable

from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.util.file import read_file, write_file

if TYPE_CHECKING:
    from zrb.session_state_log.session_state_log import (
        SessionStateLog,
        SessionStateLogList,
    )


class FileSessionStateLogger(AnySessionStateLogger):
    def __init__(
        self,
        session_log_dir: str | Callable[[], str],
        retention_seconds: int | Callable[[], int] = 0,
        prune_interval_seconds: int | Callable[[], int] = 86400,
    ):
        """*retention_seconds* (or a callable giving it) is how long a
        session's log is kept; older ones are pruned the first time a session
        is written to a directory, at most once per *prune_interval_seconds*
        (or a callable giving it) — 0 prunes on every process's first write.
        A retention of 0 keeps every log."""
        self.session_log_dir_param = session_log_dir
        self._retention_seconds = retention_seconds
        self._prune_interval_seconds = prune_interval_seconds
        self._pruned_dirs: set[str] = set()

    def get_session_log_dir(self) -> str:
        """Get the session log directory as a string.

        If session_log_dir was provided as a callable, it will be called.
        If it was provided as a string, it will be returned directly.
        """
        if callable(self.session_log_dir_param):
            return self.session_log_dir_param()
        return self.session_log_dir_param

    def write(self, session_log: "SessionStateLog"):
        session_log_dir = self.get_session_log_dir()
        if session_log_dir not in self._pruned_dirs:
            self._pruned_dirs.add(session_log_dir)
            self._prune_expired(session_log_dir, keep=session_log.name)
        session_file_path = self.get_session_file_path(session_log.name)
        session_dir_path = os.path.dirname(session_file_path)
        if not os.path.isdir(session_dir_path):
            os.makedirs(session_dir_path, exist_ok=True)
        write_file(session_file_path, session_log.model_dump_json())
        start_time = session_log.start_time
        if start_time == "":
            return
        timeline_dir_path = self._get_timeline_dir_path(session_log)
        write_file(os.path.join(timeline_dir_path, session_log.name), "")

    def read(self, session_name: str) -> "SessionStateLog":

        session_file_path = self.get_session_file_path(session_name)
        return _state_log_models().SessionStateLog.model_validate_json(
            read_file(session_file_path)
        )

    def list(
        self,
        task_path: list[str],
        min_start_time: datetime.datetime,
        max_start_time: datetime.datetime,
        page: int = 0,
        limit: int = 10,
    ) -> "SessionStateLogList":

        matching_sessions: list[tuple[datetime.datetime, "SessionStateLog"]] = []
        timeline_dir = os.path.join(self.get_session_log_dir(), "_timeline", *task_path)
        if not os.path.exists(timeline_dir):
            return _state_log_models().SessionStateLogList(total=0, data=[])
        for _, _, files in os.walk(timeline_dir):
            for file_name in files:
                session_name = os.path.splitext(file_name)[0]
                try:
                    session_log = self.read(session_name)
                except FileNotFoundError:
                    continue  # pruned meanwhile, by this process or another
                start_time = self._get_start_time(session_log)
                if start_time and min_start_time <= start_time <= max_start_time:
                    matching_sessions.append((start_time, session_log))
        matching_sessions.sort(key=lambda x: x[0], reverse=True)
        total = len(matching_sessions)
        start_index = page * limit
        end_index = start_index + limit
        paginated_sessions = matching_sessions[start_index:end_index]
        data = [session_log for _, session_log in paginated_sessions]
        return _state_log_models().SessionStateLogList(total=total, data=data)

    def _prune_expired(self, session_log_dir: str, keep: str) -> None:
        """Delete the logs, and their timeline entries, of sessions last
        written longer ago than the retention — never *keep*, the session
        being written. A timeline entry whose log is gone goes too: listing
        would fail on it. Errors are swallowed: pruning must not break the
        write that triggered it.

        At most once per prune interval per directory (`_PRUNE_MARKER`):
        every `zrb` command is a process of its own, and each would otherwise
        walk the whole timeline."""
        seconds = _resolve(self._retention_seconds)
        interval = _resolve(self._prune_interval_seconds)
        if seconds <= 0 or not _should_prune_now(session_log_dir, interval):
            return
        cutoff = time.time() - seconds
        timeline_dir = os.path.join(session_log_dir, "_timeline")
        for dir_path, _, file_names in os.walk(timeline_dir, topdown=False):
            for file_name in file_names:
                log_path = os.path.join(session_log_dir, f"{file_name}.json")
                if file_name != keep and _is_expired(log_path, cutoff):
                    _remove_quietly(os.path.join(dir_path, file_name))
            if dir_path != timeline_dir:
                try:
                    os.rmdir(dir_path)  # only succeeds once it is empty
                except OSError:
                    pass
        try:
            entries = list(os.scandir(session_log_dir))
        except OSError:
            return
        for entry in entries:
            name, extension = os.path.splitext(entry.name)
            if (
                extension == ".json"
                and name != keep
                and _is_expired(entry.path, cutoff)
            ):
                _remove_quietly(entry.path)

    def get_session_file_path(self, session_name: str) -> str:
        return os.path.join(self.get_session_log_dir(), f"{session_name}.json")

    def _get_timeline_dir_path(self, session_log: "SessionStateLog") -> str:
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
        return os.path.join(self.get_session_log_dir(), "_timeline", *paths)

    def _get_start_time(self, session_log: "SessionStateLog") -> datetime.datetime:
        return datetime.datetime.strptime(
            session_log.start_time, "%Y-%m-%d %H:%M:%S.%f"
        )


#: Touched when a directory is pruned; its age says when that last happened.
_PRUNE_MARKER = ".last-pruned"


def _resolve(value: int | Callable[[], int]) -> int:
    return value() if callable(value) else value


def _should_prune_now(session_log_dir: str, interval: int) -> bool:
    """Whether *session_log_dir* is due a prune — its last one more than
    *interval* seconds ago — marking it done if so."""
    marker = os.path.join(session_log_dir, _PRUNE_MARKER)
    try:
        if time.time() - os.path.getmtime(marker) < interval:
            return False
    except OSError:
        pass  # never pruned
    try:
        os.makedirs(session_log_dir, exist_ok=True)
        with open(marker, "ab"):
            pass
        os.utime(marker)
    except OSError:
        return False
    return True


def _is_expired(path: str, cutoff: float) -> bool:
    """Whether *path* was last written before *cutoff*, or is gone."""
    try:
        return os.path.getmtime(path) < cutoff
    except OSError:
        return True


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _state_log_models():
    # lazy: transitively heavy -- session_state_log declares pydantic models.
    from zrb.session_state_log import session_state_log

    return session_state_log
