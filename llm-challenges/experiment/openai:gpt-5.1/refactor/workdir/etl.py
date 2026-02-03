from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List

# -----------------
# Configuration
# -----------------


@dataclass(frozen=True)
class ETLConfig:
    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    report_file: str = "report.html"


CONFIG = ETLConfig()


# -----------------
# Extract
# -----------------

LOG_LINE_PATTERN = re.compile(
    r"^(?P<date>\S+\s+\S+)\s+(?P<level>\S+)\s+(?P<message>.+)$"
)
USER_MSG_PATTERN = re.compile(r"User\s+(?P<user_id>\S+)")


@dataclass
class LogRecord:
    date: str
    type: str
    msg: str | None = None
    user: str | None = None


def extract_logs(config: ETLConfig = CONFIG) -> List[LogRecord]:
    """Extract relevant log records from the log file.

    This replicates the original behaviour:
    - ERROR lines become records of type "ERROR" with full message text.
    - INFO lines that contain the word "User" become records of type
      "USER_ACTION" with parsed `user` id.
    """
    records: List[LogRecord] = []

    if not os.path.exists(config.log_file):
        return records

    with open(config.log_file, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue

            match = LOG_LINE_PATTERN.match(line)
            if not match:
                # Ignore malformed lines, as the original code effectively did
                continue

            date = match.group("date")
            level = match.group("level")
            message = match.group("message").strip()

            if level == "ERROR":
                # Preserve exact message text used as the error key
                records.append(LogRecord(date=date, type="ERROR", msg=message))
            elif level == "INFO":
                user_match = USER_MSG_PATTERN.search(message)
                if user_match:
                    user_id = user_match.group("user_id")
                    records.append(
                        LogRecord(date=date, type="USER_ACTION", user=user_id)
                    )

    return records


# -----------------
# Transform
# -----------------


def transform_error_counts(records: Iterable[LogRecord]) -> Dict[str, int]:
    """Aggregate error message counts.

    This mirrors the original logic that built a dict of
    `{error_message: count}` using only records of type "ERROR".
    """
    report: Dict[str, int] = {}
    for record in records:
        if record.type != "ERROR" or record.msg is None:
            continue
        if record.msg not in report:
            report[record.msg] = 0
        report[record.msg] += 1
    return report


# -----------------
# Load
# -----------------


def simulate_db_connection(config: ETLConfig = CONFIG) -> None:
    """Simulate connecting to a database.

    Behaviour preserved from the original script: simply prints.
    """
    print(f"Connecting to {config.db_host} as {config.db_user}...")


def render_html_report(error_counts: Dict[str, int]) -> str:
    """Render the HTML report string.

    The structure and content matches the original implementation so
    that `report.html` remains unchanged.
    """
    html = "<html><body><h1>Report</h1><ul>"
    for message, count in error_counts.items():
        html += f"<li>{message}: {count}</li>"
    html += "</ul></body></html>"
    return html


def load_report(error_counts: Dict[str, int], config: ETLConfig = CONFIG) -> None:
    """Write the HTML report to disk."""
    html = render_html_report(error_counts)
    with open(config.report_file, "w") as f:
        f.write(html)


# -----------------
# Orchestration
# -----------------


def run_etl(config: ETLConfig = CONFIG) -> None:
    records = extract_logs(config)
    simulate_db_connection(config)
    error_counts = transform_error_counts(records)
    load_report(error_counts, config)
    print("Done.")


if __name__ == "__main__":
    # Create dummy log file if not exists for testing
    if not os.path.exists(CONFIG.log_file):
        with open(CONFIG.log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    run_etl(CONFIG)
