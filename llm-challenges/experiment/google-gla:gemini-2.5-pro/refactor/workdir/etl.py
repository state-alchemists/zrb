# etl.py
import datetime
import os
import re
from typing import Dict, List, Optional, TypedDict, Union

import settings


class ErrorLog(TypedDict):
    """A dictionary representing a structured error log entry."""
    type: str  # "ERR"
    timestamp: str
    message: str


class UserLog(TypedDict):
    """A dictionary representing a structured user activity log entry."""
    type: str  # "USR"
    timestamp: str
    user_id: str


# A union type for any possible structured log entry
LogEntry = Union[ErrorLog, UserLog]


def extract_data(log_path: str) -> List[str]:
    """
    Extracts raw log lines from the specified log file.

    Args:
        log_path: The path to the log file.

    Returns:
        A list of non-empty lines from the log file.
    """
    if not os.path.exists(log_path):
        print(f"Warning: Log file not found at {log_path}. Returning empty list.")
        return []
    with open(log_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def transform_data(raw_logs: List[str]) -> List[LogEntry]:
    """
    Transforms raw log lines into a list of structured LogEntry dictionaries.

    Args:
        raw_logs: A list of raw log strings.

    Returns:
        A list of structured log entries (ErrorLog or UserLog).
    """
    # Regex to capture timestamp, level, and the rest of the message.
    # It's designed to be flexible with whitespace.
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+([A-Z]+)\s+(.*)$")
    
    # Regex specifically for user login messages
    user_pattern = re.compile(r"User\s+(\d+)\s+logged\s+in")

    structured_data: List[LogEntry] = []
    for line in raw_logs:
        match = log_pattern.match(line)
        if not match:
            continue

        timestamp, level, message = match.groups()

        if level == "ERROR":
            structured_data.append(
                ErrorLog(type="ERR", timestamp=timestamp, message=message.strip())
            )
        elif level == "INFO":
            user_match = user_pattern.search(message)
            if user_match:
                user_id = user_match.group(1)
                structured_data.append(
                    UserLog(type="USR", timestamp=timestamp, user_id=user_id)
                )
    return structured_data


def load_report(transformed_data: List[LogEntry], report_path: str):
    """
    Generates an HTML report from transformed data and saves it to a file.

    Args:
        transformed_data: A list of structured log entries.
        report_path: The path to save the output HTML report.
    """
    print(f"Connecting to {settings.DB_HOST} as {settings.DB_USER}...")
    
    error_counts: Dict[str, int] = {}
    for entry in transformed_data:
        if entry["type"] == "ERR":
            # We know it's an ErrorLog, but mypy might not, so we can assert
            error_log = entry
            msg = error_log["message"]
            error_counts[msg] = error_counts.get(msg, 0) + 1

    # Generate HTML content
    html_content = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    html_content += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in sorted(error_counts.items()): # sorted for deterministic output
        html_content += f"<li><b>{err_msg}</b>: {str(count)} occurrences</li>\n"
    html_content += "</ul>\n</body>\n</html>"

    with open(report_path, "w") as f:
        f.write(html_content)
    print(f"Report successfully generated at {report_path}")


def setup_dummy_log_file(log_path: str):
    """Creates a dummy log file if one doesn't exist."""
    if not os.path.exists(log_path):
        print(f"Creating dummy log file at {log_path}...")
        with open(log_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO  User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            # Added extra space to test robust parsing
            f.write("2024-01-01 12:05:05 ERROR   Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO  User 42 logged out\n") # Note: This line won't be in the report


def main():
    """Main ETL process orchestrator."""
    # Setup: Create a dummy log file for demonstration if it's missing
    setup_dummy_log_file(settings.LOG_FILE_PATH)

    # 1. Extract
    raw_data = extract_data(settings.LOG_FILE_PATH)

    # 2. Transform
    transformed_data = transform_data(raw_data)

    # 3. Load
    load_report(transformed_data, settings.REPORT_FILE_PATH)
    
    print("Job finished at " + str(datetime.datetime.now()))


if __name__ == "__main__":
    main()
