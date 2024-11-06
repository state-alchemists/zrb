from .any_session_state_logger import AnySessionStateLogger
from ..session_state_log.session_state_log import SessionStateLog
import json
import os


class FileSessionStateLogger(AnySessionStateLogger):

    def __init__(self, session_log_dir: str):
        self._session_log_dir = session_log_dir

    def write(self, session_log: SessionStateLog, session_parent_name: str | None):
        session_file_path = self._get_session_file_path(session_log["name"])
        with open(session_file_path, "w") as f:
            f.write(json.dumps(session_log))
        if session_parent_name is None:
            return
        relation_dir_path = self._get_children_dir_path(session_parent_name)
        self._prepare_children_dir(relation_dir_path)
        last_page = self._get_children_last_page(relation_dir_path)
        last_page_dir_path = os.path.join(relation_dir_path, f"{last_page}")
        os.makedirs(last_page_dir_path, exist_ok=True)
        with open(os.path.join(last_page_dir_path, session_log["name"]), "w"):
            pass

    def read(self, session_name: str) -> SessionStateLog:
        session_file_path = self._get_session_file_path(session_name)
        with open(session_file_path, "r") as f:
            return json.loads(f.read())

    def read_children(self, session_name: str, page: int) -> list[SessionStateLog]:
        pass

    def _get_session_file_path(self, session_name: str) -> str:
        return os.path.join(self._session_log_dir, f'{session_name}.json')

    def _get_children_dir_path(self, session_parent_name: str):
        return os.path.join(self._session_log_dir, "children", session_parent_name)

    def _prepare_children_dir(self, children_dir_path: str):
        os.makedirs(children_dir_path, exist_ok=True)
        last_page = self._get_children_last_page(children_dir_path)
        if last_page is None:
            os.makedirs(os.path.join(children_dir_path, "0"), exist_ok=True)
            last_page = 0
        if self._get_child_count(children_dir_path, last_page) >= 5:
            os.makedirs(os.path.join(children_dir_path, f"{last_page + 1}"), exist_ok=True)

    def _get_child_count(self, children_dir_path: str, page: int) -> int:
        path = os.path.join(children_dir_path, str(page))
        return sum(
            1 for entry in os.listdir(path) if os.path.isfile(os.path.join(path, entry))
        )

    def _get_children_last_page(self, children_dir_path: str) -> int:
        last_page = self._get_children_existing_last_page(children_dir_path)
        if last_page is None:
            os.makedirs(os.path.join(children_dir_path, "0"), exist_ok=True)
            last_page = 0
        return last_page

    def _get_children_existing_last_page(self, children_dir_path: str) -> int | None:
        numeric_dirs = [
            int(name) for name in os.listdir(children_dir_path)
            if os.path.isdir(os.path.join(children_dir_path, name)) and name.isdigit()
        ]
        return max(numeric_dirs, default=None)
