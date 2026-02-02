import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from etl_config import DB_CONFIG, LOG_FILE, REPORT_FILE


@dataclass
class LogRecord:
    date: str
    level: str
    message: str


@dataclass
class UserAction:
    date: str
    user_id: str


LOG_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|ERROR)\s+"
    r"(?P<message>.*)$"
)

USER_ACTION_PATTERN = re.compile(r"User\s+(?P<user_id>\S+)")


def extract_log_records(log_path: str = LOG_FILE) -> List[LogRecord]:
    """Extract structured log records from a log file.

    This uses regular expressions instead of fragile string splitting.
    """
    records: List[LogRecord] = []
    if not os.path.exists(log_path):
        return records

    with open(log_path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            match = LOG_LINE_PATTERN.match(line)
            if not match:
                continue
            records.append(
                LogRecord(
                    date=match.group("date"),
                    level=match.group("level"),
                    message=match.group("message").strip(),
                )
            )
    return records


def transform(records: Iterable[LogRecord]) -> Dict[str, int]:
    """Transform log records into an error summary.

    The original script only used ERROR messages to build the report,
    so this keeps the same behaviour.
    """
    error_counter: Counter[str] = Counter()
    for record in records:
        if record.level == "ERROR":
            error_counter[record.message] += 1
    return dict(error_counter)


def extract_user_actions(records: Iterable[LogRecord]) -> List[UserAction]:
    """Optional helper to derive user actions from INFO messages.

    This preserves the original user parsing logic but keeps it out of the
    main ETL pipeline. Currently not used in the report generation.
    """
    actions: List[UserAction] = []
    for record in records:
        if record.level != "INFO":
            continue
        match = USER_ACTION_PATTERN.search(record.message)
        if not match:
            continue
        actions.append(UserAction(date=record.date, user_id=match.group("user_id")))
    return actions


def load_error_report(
    error_summary: Dict[str, int], report_path: str = REPORT_FILE
) -> None:
    """Load step: generate the HTML report from the error summary.

    The HTML structure is kept identical to the original implementation.
    """
    html = "<html><body><h1>Report</h1><ul>"
    for message, count in error_summary.items():
        html += f"<li>{message}: {count}</li>"
    html += "</ul></body></html>"

    with open(report_path, "w") as f:
        f.write(html)


def run_etl() -> None:
    """End-to-end ETL pipeline: Extract -> Transform -> Load."""
    # Extract
    records = extract_log_records()

    # Simulate DB connection (side-effect preserved for compatibility)
    print(f"Connecting to {DB_CONFIG.host} as {DB_CONFIG.user}...")

    # Transform
    error_summary = transform(records)

    # Load
    load_error_report(error_summary)

    print("Done.")


if __name__ == "__main__":
    # Create dummy log file if not exists for testing (preserved behaviour)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    run_etl()
