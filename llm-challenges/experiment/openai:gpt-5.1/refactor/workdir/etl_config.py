from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class DBConfig:
    host: str
    user: str


# Default configuration values
DB_CONFIG: Final[DBConfig] = DBConfig(host="localhost", user="admin")
LOG_FILE: Final[str] = "server.log"
REPORT_FILE: Final[str] = "report.html"
