#!/usr/bin/env python3
"""
Refactored ETL script for processing server logs.

This script follows the ETL (Extract, Transform, Load) pattern to:
1. Extract log entries from a server log file
2. Transform log entries into structured data
3. Load data into a report format (HTML)

Features:
- Configuration via environment variables or defaults
- Regex-based parsing for robustness
- Type hints and comprehensive docstrings
- Separation of concerns with clear function boundaries
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, TypedDict

# ============================================================================
# Configuration
# ============================================================================


@dataclass
class Config:
    """Configuration for the ETL process."""

    db_host: str
    db_user: str
    log_file: str
    report_file: str

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables with fallbacks."""
        return cls(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_user=os.getenv("DB_USER", "admin"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            report_file=os.getenv("REPORT_FILE", "report.html"),
        )


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class LogEntry:
    """Represents a parsed log entry."""

    timestamp: str
    level: str
    message: str

    @property
    def is_error(self) -> bool:
        """Check if this is an ERROR level entry."""
        return self.level == "ERROR"

    @property
    def is_info(self) -> bool:
        """Check if this is an INFO level entry."""
        return self.level == "INFO"

    @property
    def contains_user(self) -> bool:
        """Check if message contains user information."""
        return "User" in self.message


@dataclass
class ProcessedData:
    """Represents processed data ready for reporting."""

    error_counts: Dict[str, int]
    user_actions: List[Dict[str, str]]


# ============================================================================
# ETL Functions
# ============================================================================


def extract_log_entries(log_file_path: str) -> List[LogEntry]:
    """
    Extract log entries from a log file.

    Args:
        log_file_path: Path to the log file

    Returns:
        List of parsed LogEntry objects

    Raises:
        FileNotFoundError: If the log file doesn't exist
    """
    if not os.path.exists(log_file_path):
        raise FileNotFoundError(f"Log file not found: {log_file_path}")

    entries: List[LogEntry] = []

    # Regex pattern for log entries: YYYY-MM-DD HH:MM:SS LEVEL message
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$")

    with open(log_file_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            match = log_pattern.match(line)
            if match:
                timestamp, level, message = match.groups()
                entries.append(LogEntry(timestamp, level, message))
            else:
                print(
                    f"Warning: Line {line_num} doesn't match log format: {line[:50]}..."
                )

    return entries


def transform_log_data(entries: List[LogEntry]) -> ProcessedData:
    """
    Transform log entries into structured data for reporting.

    Args:
        entries: List of LogEntry objects

    Returns:
        ProcessedData containing error counts (matches original behavior)
    """
    error_counts: Dict[str, int] = {}

    for entry in entries:
        if entry.is_error:
            # Count error occurrences (exact same logic as original)
            if entry.message not in error_counts:
                error_counts[entry.message] = 0
            error_counts[entry.message] += 1

    # Original script didn't process user actions for the report
    return ProcessedData(error_counts, [])


def generate_html_report(processed_data: ProcessedData) -> str:
    """
    Generate HTML report from processed data.

    Args:
        processed_data: ProcessedData containing error counts and user actions

    Returns:
        HTML string for the report (matches original format exactly)
    """
    # Match the exact original format: <html><body><h1>Report</h1><ul>...</ul></body></html>
    html = "<html><body><h1>Report</h1><ul>"

    for error_msg, count in processed_data.error_counts.items():
        html += f"<li>{error_msg}: {count}</li>"

    html += "</ul></body></html>"

    return html


def load_report_to_file(report_content: str, report_file_path: str) -> None:
    """
    Save HTML report to a file.

    Args:
        report_content: HTML string to save
        report_file_path: Path where to save the report
    """
    with open(report_file_path, "w") as f:
        f.write(report_content)
    print(f"Report saved to: {report_file_path}")


def simulate_database_connection(config: Config) -> None:
    """
    Simulate database connection (placeholder for actual DB operations).

    Args:
        config: Configuration containing DB connection details
    """
    print(f"Connecting to {config.db_host} as {config.db_user}...")


def create_sample_log_file(log_file_path: str) -> None:
    """
    Create a sample log file if it doesn't exist (for testing).

    Args:
        log_file_path: Path to the log file
    """
    if not os.path.exists(log_file_path):
        sample_logs = [
            "2023-10-01 10:00:00 INFO User 123 logged in\n",
            "2023-10-01 10:05:00 ERROR Connection failed\n",
            "2023-10-01 10:10:00 ERROR Connection failed\n",
            "2023-10-01 10:15:00 INFO User 456 performed transaction\n",
            "2023-10-01 10:20:00 WARNING High memory usage detected\n",
            "2023-10-01 10:25:00 INFO User 123 logged out\n",
        ]

        with open(log_file_path, "w") as f:
            f.writelines(sample_logs)
        print(f"Created sample log file: {log_file_path}")


# ============================================================================
# Main ETL Pipeline
# ============================================================================


def run_etl_pipeline(config: Config) -> None:
    """
    Run the complete ETL pipeline.

    Args:
        config: Configuration for the ETL process
    """
    print("Starting ETL pipeline...")

    # Create sample log if needed
    create_sample_log_file(config.log_file)

    # Simulate database connection
    simulate_database_connection(config)

    try:
        # EXTRACT: Read and parse log entries
        print(f"Extracting log entries from: {config.log_file}")
        log_entries = extract_log_entries(config.log_file)
        print(f"Extracted {len(log_entries)} log entries")

        # TRANSFORM: Process log data
        print("Transforming log data...")
        processed_data = transform_log_data(log_entries)
        print(f"Found {len(processed_data.error_counts)} unique error types")
        print(f"Found {len(processed_data.user_actions)} user actions")

        # LOAD: Generate and save report
        print("Generating HTML report...")
        html_report = generate_html_report(processed_data)
        load_report_to_file(html_report, config.report_file)

        print("ETL pipeline completed successfully!")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the ETL script."""
    # Load configuration
    config = Config.from_env()

    # Run the ETL pipeline
    run_etl_pipeline(config)


if __name__ == "__main__":
    main()
