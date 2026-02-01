import os
from dataclasses import dataclass

@dataclass
class Config:
    """
    Configuration for the ETL process.
    Values can be overridden by environment variables.
    """
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_user: str = os.getenv("DB_USER", "admin")
    log_file: str = os.getenv("LOG_FILE", "server.log")
    report_file: str = os.getenv("REPORT_FILE", "report.html")
