"""
ETL Pipeline: Extract, Transform, Load server logs and generate HTML reports.

This module implements a clean ETL pattern to process server log files,
parse them using regex, and generate HTML error reports.
"""

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# ==================== CONFIGURATION ====================


@dataclass
class Config:
    """Configuration for the ETL pipeline."""

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    output_file: str = "report.html"

    # HTML templates
    html_template: str = (
        "<html><body><h1>Report</h1><ul>" "{items}" "</ul></body></html>"
    )
    html_item_template: str = "<li>{key}: {value}</li>"


# ==================== DATA MODELS ====================


@dataclass
class LogEntry:
    """Represents a parsed log entry."""

    date: str
    log_type: str
    message: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class ErrorReport:
    """Represents the generated error report."""

    error_counts: Dict[str, int]

    def to_list_items(self) -> List[str]:
        """Convert error counts to HTML list items."""
        return [
            f"<li>{msg}: {count}</li>"
            for msg, count in sorted(self.error_counts.items())
        ]


# ==================== EXTRACT ====================


class LogParser:
    """Parses log files using regex patterns."""

    # Pattern: YYYY-MM-DD HH:MM:SS [TYPE] [message content]
    LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) (\w+) (.+)$")

    # Pattern: User [id] logged in
    USER_PATTERN = re.compile(r"User (\d+) ")

    @classmethod
    def parse_line(cls: "LogParser", line: str) -> Optional[LogEntry]:
        """
        Parse a single log line into a LogEntry.

        Args:
            line: Raw log line string

        Returns:
            LogEntry if parsing succeeds, None otherwise
        """
        line = line.strip()
        if not line:
            return None

        match = cls.LOG_PATTERN.match(line)
        if not match:
            return None

        date_part, time_part, log_type, message = match.groups()
        date = f"{date_part} {time_part}"

        user_id = None
        if log_type == "INFO" and "User" in message:
            user_match = cls.USER_PATTERN.search(message)
            if user_match:
                user_id = user_match.group(1)

        return LogEntry(date=date, log_type=log_type, message=message, user_id=user_id)

    @classmethod
    def parse_file(cls: "LogParser", file_path: str) -> List[LogEntry]:
        """
        Parse an entire log file.

        Args:
            file_path: Path to the log file

        Returns:
            List of parsed LogEntry objects
        """
        entries = []
        log_path = Path(file_path)

        if not log_path.exists():
            return entries

        with open(log_path, "r") as f:
            for line in f:
                entry = cls.parse_line(line)
                if entry:
                    entries.append(entry)

        return entries


def extract(config: Config) -> List[LogEntry]:
    """
    Extract log entries from the configured log file.

    Args:
        config: Pipeline configuration

    Returns:
        List of parsed log entries
    """
    return LogParser.parse_file(config.log_file)


# ==================== TRANSFORM ====================


def transform(entries: List[LogEntry]) -> ErrorReport:
    """
    Transform log entries into an error report.

    Args:
        entries: List of log entries to process

    Returns:
        ErrorReport with counted error messages
    """
    # Filter and count error messages
    error_messages = [
        entry.message
        for entry in entries
        if entry.log_type == "ERROR" and entry.message
    ]

    error_counts = Counter(error_messages)

    return ErrorReport(error_counts=dict(error_counts))


# ==================== LOAD ====================


def simulate_database_connection(config: Config) -> None:
    """
    Simulate a database connection.

    Args:
        config: Pipeline configuration
    """
    print(f"Connecting to {config.db_host} as {config.db_user}...")


def save_report(report: ErrorReport, config: Config) -> None:
    """
    Save the error report as an HTML file.

    Args:
        report: ErrorReport to save
        config: Pipeline configuration
    """
    # Build HTML content
    list_items = "\n".join(report.to_list_items())
    html_content = config.html_template.format(items=list_items)

    # Write to file
    with open(config.output_file, "w") as f:
        f.write(html_content)


def load(report: ErrorReport, config: Config) -> None:
    """
    Load the transformed data into output formats.

    Args:
        report: ErrorReport to load
        config: Pipeline configuration
    """
    simulate_database_connection(config)
    save_report(report, config)


# ==================== ETL ORCHESTRATOR ====================


def run_etl(config: Config) -> None:
    """
    Execute the complete ETL pipeline.

    Args:
        config: Pipeline configuration
    """
    # Extract: Read and parse log file
    entries = extract(config)

    # Transform: Process entries into report
    report = transform(entries)

    # Load: Save report
    load(report, config)

    print("Done.")


# ==================== MAIN ====================


def main() -> None:
    """Main entry point for the ETL pipeline."""
    config = Config()

    # Create dummy log file if not exists for testing
    log_path = Path(config.log_file)
    if not log_path.exists():
        with open(config.log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    # Run ETL pipeline
    run_etl(config)


if __name__ == "__main__":
    main()
