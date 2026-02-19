from zrb.config.config import CFG
from zrb.session_state_logger.file_session_state_logger import FileSessionStateLogger

session_state_logger = FileSessionStateLogger(lambda: CFG.SESSION_LOG_DIR)
