from zrb.config.config import CFG
from zrb.session_state_logger.file_session_state_logger import FileSessionStateLogger
from zrb.util.todo.duration import parse_duration

session_state_logger = FileSessionStateLogger(
    lambda: CFG.SESSION_LOG_DIR,
    retention_seconds=lambda: parse_duration(CFG.SESSION_LOG_RETENTION or ""),
    prune_interval_seconds=lambda: parse_duration(CFG.SESSION_LOG_PRUNE_INTERVAL or ""),
)
