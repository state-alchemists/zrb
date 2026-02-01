import re

LOG_FILE = "server.log"
DB_HOST = "localhost"
DB_USER = "admin"

# Regex patterns for log parsing
LOG_ENTRY_REGEX = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>INFO|ERROR) (?P<message>.*)$"
)
USER_ACTION_REGEX = re.compile(r".*User (?P<user_id>\d+) logged in.*")
