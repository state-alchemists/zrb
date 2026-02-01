"""ETL pipeline for processing log files and generating error reports."""

import os
import re
from typing import Dict, List, Optional, TypedDict

from config import AppConfig, DatabaseConfig


class LogEntry(TypedDict):
    """Represents a parsed log entry."""

    date: str
    type: str
    msg: Optional[str]
    user: Optional[str]


def get_default_config() -> AppConfig:
    """Returns default application configuration."""
    db_config = DatabaseConfig(host="localhost", user="admin")
    return AppConfig(
        db_config=db_config, log_file="server.log", report_file="report.html"
    )


def extract_log_data(config: AppConfig) -> List[LogEntry]:
    """
    Extract and parse log data from file.

    Args:
        config: Application configuration containing log file path.

    Returns:
        List of parsed log entries.
    """
    if not os.path.exists(config.log_file):
        return []

    entries: List[LogEntry] = []

    # Regex patterns for parsing
    error_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<msg>.+)$"
    )
    info_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<user>\d+) (?P<msg>.+)$"
    )

    with open(config.log_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Try ERROR pattern first
            error_match = error_pattern.match(line)
            if error_match:
                entries.append(
                    {
                        "date": error_match.group("date"),
                        "type": "ERROR",
                        "msg": error_match.group("msg"),
                        "user": None,
                    }
                )
                continue

            # Try INFO pattern
            info_match = info_pattern.match(line)
            if info_match:
                entries.append(
                    {
                        "date": info_match.group("date"),
                        "type": "USER_ACTION",
                        "msg": None,
                        "user": info_match.group("user"),
                    }
                )

    return entries


def transform_data(entries: List[LogEntry]) -> Dict[str, int]:
    """
    Transform log entries into error count report.

    Args:
        entries: List of parsed log entries.

    Returns:
        Dictionary mapping error messages to their occurrence counts.
    """
    report: Dict[str, int] = {}

    for entry in entries:
        if entry["type"] == "ERROR" and entry["msg"]:
            msg = entry["msg"]
            if msg not in report:
                report[msg] = 0
            report[msg] += 1

    return report


def load_report(config: AppConfig, report_data: Dict[str, int]) -> None:
    """
    Load/generate HTML report from transformed data.

    Args:
        config: Application configuration containing DB info and report file path.
        report_data: Dictionary of error messages and their counts.
    """
    # Simulate database connection
    db_config = config.db_config
    print(f"Connecting to {db_config.host} as {db_config.user}...")

    # Generate HTML report
    html_lines = ["<html>", "<body>", "<h1>Report</h1>", "<ul>"]

    for error_msg, count in report_data.items():
        html_lines.append(f"<li>{error_msg}: {count}</li>")

    html_lines.extend(["</ul>", "</body>", "</html>"])

    html = "\n".join(html_lines)

    with open(config.report_file, "w") as f:
        f.write(html)


def run_etl_pipeline(config: Optional[AppConfig] = None) -> None:
    """
    Run the complete ETL pipeline.

    Args:
        config: Optional application configuration. Uses default if not provided.
    """
    if config is None:
        config = get_default_config()

    # Extract: Read and parse log data
    entries = extract_log_data(config)

    # Transform: Aggregate error counts
    report_data = transform_data(entries)

    # Load: Generate HTML report
    load_report(config, report_data)

    print("Done.")


def create_dummy_log_file(log_file: str) -> None:
    """
    Create dummy log file for testing purposes.

    Args:
        log_file: Path to the log file to create.
    """
    with open(log_file, "w") as f:
        f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
        f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
        f.write("2023-10-01 10:10:00 ERROR Connection failed\n")


if __name__ == "__main__":
    config = get_default_config()

    # Create dummy log file if not exists for testing
    if not os.path.exists(config.log_file):
        create_dummy_log_file(config.log_file)

    run_etl_pipeline(config)
