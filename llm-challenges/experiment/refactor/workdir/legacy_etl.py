"""
ETL (Extract, Transform, Load) pipeline for processing server logs.

This module provides a refactored version of the legacy ETL script with:
- Separated extraction, transformation, and loading phases
- Configuration via environment variables
- Improved log parsing using regex
- Type hints and comprehensive docstrings
"""

import datetime
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Union


# Type definitions for better type safety
class LogEntry(TypedDict):
    """Represents a parsed log entry."""

    timestamp: str
    log_type: str
    message: str
    user_id: Optional[str]


class ErrorReport(TypedDict):
    """Represents an error report entry."""

    error_message: str
    count: int


@dataclass
class Config:
    """Configuration for the ETL pipeline."""

    db_host: str
    db_user: str
    log_file: str
    report_file: str = "report.html"

    @classmethod
    def from_env(cls) -> "Config":
        """
        Create configuration from environment variables.

        Returns:
            Config: Configuration object with values from environment variables
                   or defaults if not set.
        """
        return cls(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_user=os.getenv("DB_USER", "admin"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            report_file=os.getenv("REPORT_FILE", "report.html"),
        )


def extract_logs(log_file_path: str) -> List[str]:
    """
    Extract log lines from a file.

    Args:
        log_file_path: Path to the log file

    Returns:
        List of log lines as strings

    Raises:
        FileNotFoundError: If the log file doesn't exist
    """
    if not os.path.exists(log_file_path):
        raise FileNotFoundError(f"Log file not found: {log_file_path}")

    with open(log_file_path, "r") as file:
        return [line.strip() for line in file.readlines() if line.strip()]


def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line using regex.

    Expected format: "YYYY-MM-DD HH:MM:SS TYPE message"

    Args:
        line: A single log line

    Returns:
        Parsed LogEntry or None if line doesn't match expected format
    """
    # Regex pattern for log lines: date time type message
    pattern = r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.+)$"
    match = re.match(pattern, line)

    if not match:
        return None

    date_str, time_str, log_type, message = match.groups()
    timestamp = f"{date_str} {time_str}"

    # Extract user ID if present in INFO messages
    user_id = None
    if log_type == "INFO" and "User" in message:
        user_match = re.search(r"User\s+(\d+)", message)
        if user_match:
            user_id = user_match.group(1)

    return LogEntry(
        timestamp=timestamp, log_type=log_type, message=message, user_id=user_id
    )


def transform_logs(log_lines: List[str]) -> List[LogEntry]:
    """
    Transform raw log lines into structured log entries.

    Args:
        log_lines: List of raw log lines

    Returns:
        List of parsed LogEntry objects
    """
    parsed_entries: List[LogEntry] = []

    for line in log_lines:
        entry = parse_log_line(line)
        if entry:
            parsed_entries.append(entry)

    return parsed_entries


def generate_error_report(log_entries: List[LogEntry]) -> List[ErrorReport]:
    """
    Generate error report from log entries.

    Args:
        log_entries: List of parsed log entries

    Returns:
        List of error reports with counts
    """
    error_counts: Dict[str, int] = {}

    for entry in log_entries:
        if entry["log_type"] == "ERROR":
            error_message = entry["message"]
            error_counts[error_message] = error_counts.get(error_message, 0) + 1

    # Convert to list of ErrorReport dictionaries
    return [
        {"error_message": error_msg, "count": count}
        for error_msg, count in error_counts.items()
    ]


def generate_html_report(error_reports: List[ErrorReport], report_file: str) -> None:
    """
    Generate HTML report from error reports.

    Args:
        error_reports: List of error reports
        report_file: Path where to save the HTML report
    """
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<title>Error Report</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 40px; }",
        "h1 { color: #333; }",
        "ul { list-style-type: none; padding: 0; }",
        "li { padding: 8px; margin: 4px 0; background: #f5f5f5; border-radius: 4px; }",
        ".count { font-weight: bold; color: #d32f2f; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Error Report</h1>",
        "<p>Generated on: "
        + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        + "</p>",
        "<ul>",
    ]

    for report in error_reports:
        html_lines.append(
            f'<li><span class="count">{report["count"]}x</span> {report["error_message"]}</li>'
        )

    html_lines.extend(
        [
            "</ul>",
            f"<p>Total unique errors: {len(error_reports)}</p>",
            "</body>",
            "</html>",
        ]
    )

    with open(report_file, "w") as file:
        file.write("\n".join(html_lines))


def load_to_database(log_entries: List[LogEntry], config: Config) -> None:
    """
    Simulate loading data to database.

    Args:
        log_entries: List of parsed log entries
        config: Configuration object
    """
    print(f"Connecting to {config.db_host} as {config.db_user}...")
    print(f"Would insert {len(log_entries)} log entries to database")

    # In a real implementation, this would connect to a database
    # and insert the log entries
    error_count = sum(1 for entry in log_entries if entry["log_type"] == "ERROR")
    info_count = sum(1 for entry in log_entries if entry["log_type"] == "INFO")

    print(f"Statistics: {error_count} errors, {info_count} info messages")


def create_sample_log_file(log_file_path: str) -> None:
    """
    Create a sample log file for testing/demo purposes.

    Args:
        log_file_path: Path where to create the sample log file
    """
    sample_logs = [
        "2023-10-01 10:00:00 INFO User 123 logged in",
        "2023-10-01 10:05:00 ERROR Connection failed",
        "2023-10-01 10:10:00 ERROR Connection failed",
        "2023-10-01 10:15:00 INFO User 456 logged out",
        "2023-10-01 10:20:00 ERROR Database timeout",
        "2023-10-01 10:25:00 INFO User 789 accessed resource",
        "2023-10-01 10:30:00 WARNING High memory usage detected",
        "2023-10-01 10:35:00 ERROR Connection failed",
        "2023-10-01 10:40:00 INFO User 123 performed action",
    ]

    with open(log_file_path, "w") as file:
        file.write("\n".join(sample_logs))

    print(f"Created sample log file: {log_file_path}")


def run_etl_pipeline(config: Optional[Config] = None) -> None:
    """
    Run the complete ETL pipeline.

    Args:
        config: Configuration object. If None, uses Config.from_env()
    """
    if config is None:
        config = Config.from_env()

    print(f"Starting ETL pipeline with config:")
    print(f"  Log file: {config.log_file}")
    print(f"  DB host: {config.db_host}")
    print(f"  DB user: {config.db_user}")
    print(f"  Report file: {config.report_file}")

    try:
        # Extract phase
        print("\n1. Extracting logs...")
        log_lines = extract_logs(config.log_file)
        print(f"   Extracted {len(log_lines)} log lines")

        # Transform phase
        print("\n2. Transforming logs...")
        log_entries = transform_logs(log_lines)
        print(f"   Parsed {len(log_entries)} log entries")

        # Load phase (simulated)
        print("\n3. Loading to database...")
        load_to_database(log_entries, config)

        # Generate report
        print("\n4. Generating report...")
        error_reports = generate_error_report(log_entries)
        generate_html_report(error_reports, config.report_file)
        print(f"   Generated report: {config.report_file}")
        print(f"   Found {len(error_reports)} unique errors")

        print("\nETL pipeline completed successfully!")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(
            "Please ensure the log file exists or create a sample with --create-sample"
        )
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def main() -> None:
    """
    Main entry point for the ETL pipeline.

    Command line arguments:
        --create-sample: Create a sample log file instead of running ETL
        --config-file: Path to configuration file (not implemented in this version)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="ETL pipeline for processing server logs"
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Create a sample log file instead of running ETL",
    )
    parser.add_argument(
        "--config-file", type=str, help="Path to configuration file (JSON/YAML)"
    )

    args = parser.parse_args()

    config = Config.from_env()

    if args.create_sample:
        create_sample_log_file(config.log_file)
    else:
        run_etl_pipeline(config)


if __name__ == "__main__":
    main()
