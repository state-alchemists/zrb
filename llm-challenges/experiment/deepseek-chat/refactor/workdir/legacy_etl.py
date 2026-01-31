#!/usr/bin/env python3
"""
ETL (Extract, Transform, Load) pipeline for processing server logs.

This module extracts error and user action information from server logs,
transforms the data, and generates an HTML report of error frequencies.
"""

import datetime
import os
import re
import sys
from typing import Dict, List, Optional, TypedDict, Union


class LogEntry(TypedDict, total=False):
    """Type definition for parsed log entries."""

    date: str
    type: str
    msg: Optional[str]
    user: Optional[str]


class Config:
    """Configuration manager for the ETL pipeline."""

    def __init__(self):
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_user = os.getenv("DB_USER", "admin")
        self.log_file = os.getenv("LOG_FILE", "server.log")
        self.report_file = os.getenv("REPORT_FILE", "report.html")


def extract_log_entries(log_file_path: str) -> List[LogEntry]:
    """
    Extract log entries from a log file.

    Args:
        log_file_path: Path to the log file

    Returns:
        List of parsed log entries
    """
    entries: List[LogEntry] = []

    if not os.path.exists(log_file_path):
        print(f"Warning: Log file '{log_file_path}' not found")
        return entries

    # Regex patterns for log parsing
    log_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.+)$"
    )
    user_pattern = re.compile(r"User\s+(\d+)")

    with open(log_file_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            match = log_pattern.match(line)
            if not match:
                print(f"Warning: Line {line_num} doesn't match expected format: {line}")
                continue

            date_str, time_str, log_type, message = match.groups()
            full_date = f"{date_str} {time_str}"

            if log_type == "ERROR":
                entries.append(
                    {"date": full_date, "type": "ERROR", "msg": message.strip()}
                )
            elif log_type == "INFO":
                user_match = user_pattern.search(message)
                if user_match:
                    user_id = user_match.group(1)
                    entries.append(
                        {"date": full_date, "type": "USER_ACTION", "user": user_id}
                    )

    return entries


def transform_log_data(entries: List[LogEntry]) -> Dict[str, int]:
    """
    Transform log entries into a report-ready format.

    Args:
        entries: List of parsed log entries

    Returns:
        Dictionary mapping error messages to their frequencies
    """
    error_counts: Dict[str, int] = {}

    for entry in entries:
        if entry["type"] == "ERROR" and "msg" in entry:
            error_msg = entry["msg"]
            error_counts[error_msg] = error_counts.get(error_msg, 0) + 1

    return error_counts


def generate_html_report(error_counts: Dict[str, int], report_path: str) -> None:
    """
    Generate an HTML report from error counts.

    Args:
        error_counts: Dictionary mapping error messages to frequencies
        report_path: Path where the HTML report should be saved
    """
    if not error_counts:
        print("No error data to report")
        return

    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "    <title>Server Error Report</title>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; margin: 40px; }",
        "        h1 { color: #333; }",
        "        ul { list-style-type: none; padding: 0; }",
        "        li { padding: 8px; margin: 4px 0; background: #f5f5f5; border-radius: 4px; }",
        "        .count { float: right; font-weight: bold; color: #d32f2f; }",
        "    </style>",
        "</head>",
        "<body>",
        "    <h1>Server Error Report</h1>",
        "    <p>Generated on: "
        + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        + "</p>",
        "    <ul>",
    ]

    for error_msg, count in sorted(
        error_counts.items(), key=lambda x: x[1], reverse=True
    ):
        html_lines.append(
            f'        <li>{error_msg} <span class="count">{count}</span></li>'
        )

    html_lines.extend(["    </ul>", "</body>", "</html>"])

    with open(report_path, "w") as f:
        f.write("\n".join(html_lines))

    print(f"Report generated: {report_path}")


def load_to_database(config: Config, entries: List[LogEntry]) -> None:
    """
    Simulate loading data to a database.

    Args:
        config: Configuration object
        entries: List of log entries to load
    """
    print(f"Connecting to {config.db_host} as {config.db_user}...")
    print(f"Would load {len(entries)} log entries to database")
    # In a real implementation, this would contain actual database insertion logic


def create_sample_log_file(log_file_path: str) -> None:
    """
    Create a sample log file for testing if it doesn't exist.

    Args:
        log_file_path: Path where the sample log file should be created
    """
    sample_logs = [
        "2023-10-01 10:00:00 INFO User 123 logged in",
        "2023-10-01 10:05:00 ERROR Connection failed",
        "2023-10-01 10:10:00 ERROR Connection failed",
        "2023-10-01 10:15:00 INFO User 456 logged out",
        "2023-10-01 10:20:00 ERROR Database timeout",
        "2023-10-01 10:25:00 INFO User 789 accessed resource",
        "2023-10-01 10:30:00 ERROR Connection failed",
        "2023-10-01 10:35:00 INFO User 123 performed action",
    ]

    with open(log_file_path, "w") as f:
        f.write("\n".join(sample_logs))

    print(f"Created sample log file: {log_file_path}")


def run_etl_pipeline(config: Optional[Config] = None) -> None:
    """
    Run the complete ETL pipeline.

    Args:
        config: Optional configuration object (creates default if None)
    """
    if config is None:
        config = Config()

    print("Starting ETL pipeline...")

    # Extract phase
    print(f"Extracting logs from: {config.log_file}")
    log_entries = extract_log_entries(config.log_file)
    print(f"Extracted {len(log_entries)} log entries")

    # Transform phase
    print("Transforming log data...")
    error_counts = transform_log_data(log_entries)
    print(f"Found {len(error_counts)} unique error types")

    # Load phase (simulated)
    load_to_database(config, log_entries)

    # Report generation
    print(f"Generating report to: {config.report_file}")
    generate_html_report(error_counts, config.report_file)

    print("ETL pipeline completed successfully")


def main() -> None:
    """Main entry point for the ETL script."""
    config = Config()

    # Create sample data if log file doesn't exist
    if not os.path.exists(config.log_file):
        create_sample_log_file(config.log_file)

    # Run the ETL pipeline
    run_etl_pipeline(config)


if __name__ == "__main__":
    main()
