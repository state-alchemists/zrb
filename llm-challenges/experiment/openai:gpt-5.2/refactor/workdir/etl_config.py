from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ETLConfig:
    """Configuration for the ETL pipeline.

    Kept in a separate module to avoid hardcoded config scattered across the code.
    """

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    report_file: str = "report.html"
