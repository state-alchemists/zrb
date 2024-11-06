from ..config import SESSION_LOG_DIR
from .file_session_state_logger import FileSessionStateLogger

default_session_state_logger = FileSessionStateLogger(SESSION_LOG_DIR)
