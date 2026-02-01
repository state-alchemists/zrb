# etl_refactored/config.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Configuration for the ETL process."""

    LOG_FILE: str = "server.log"
    REPORT_FILE: str = "report.html"
    DB_HOST: str = "localhost"
    DB_USER: str = "admin"
    REPORT_TITLE: str = "Report"
