# etl_refactored/transform.py
from collections import Counter
from typing import List

from .models import LogEntry, ReportData


def transform_data(logs: List[LogEntry]) -> ReportData:
    """
    Transforms a list of logs into a report.

    Args:
        logs: A list of parsed log entries.

    Returns:
        A dictionary containing the report data.
    """
    error_messages = [log.message for log in logs if log.log_type == "ERROR"]
    return Counter(error_messages)
