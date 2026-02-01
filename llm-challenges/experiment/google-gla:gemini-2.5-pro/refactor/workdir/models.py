# etl_refactored/models.py
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


@dataclass
class LogEntry:
    """Represents a single parsed log entry."""

    date: str
    message: str
    log_type: Literal["ERROR", "USER_ACTION"]
    user_id: Optional[str] = None


# Type alias for the report data
ReportData = Dict[str, int]
