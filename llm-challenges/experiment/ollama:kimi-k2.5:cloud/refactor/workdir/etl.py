"""ETL pipeline for processing server logs and generating HTML reports."""

import datetime
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Protocol

# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: Path = Path("server.log")
    report_file: Path = Path("report.html")


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class LogEntry:
    """Represents a parsed log entry."""

    timestamp: datetime.datetime
    level: str
    message: str


@dataclass
class ErrorReport:
    """Represents an error entry for the report."""

    message: str
    count: int


# =============================================================================
# Extract
# =============================================================================


class LogExtractor:
    """Extracts log entries from a log file using regex parsing."""

    # Regex pattern: YYYY-MM-DD HH:MM:SS LEVEL Message...
    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$"
    )

    def __init__(self, log_file: Path) -> None:
        self._log_file = log_file

    def extract(self) -> List[LogEntry]:
        """Extract log entries from the configured log file."""
        entries: List[LogEntry] = []

        if not self._log_file.exists():
            return entries

        content = self._log_file.read_text()
        for line in content.strip().split("\n"):
            entry = self._parse_line(line)
            if entry:
                entries.append(entry)

        return entries

    def _parse_line(self, line: str) -> LogEntry | None:
        """Parse a single log line using regex."""
        match = self.LOG_PATTERN.match(line.strip())
        if not match:
            return None

        timestamp_str, level, message = match.groups()
        timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

        return LogEntry(
            timestamp=timestamp, level=level.upper(), message=message.strip()
        )


# =============================================================================
# Transform
# =============================================================================


class LogTransformer:
    """Transforms log entries into reportable data structures."""

    # Regex to extract user ID from user action messages
    USER_PATTERN = re.compile(r"User\s+(\d+)", re.IGNORECASE)

    def __init__(self) -> None:
        self._error_counts: Dict[str, int] = {}
        self._user_actions: List[Dict[str, str]] = []

    def transform(self, entries: List[LogEntry]) -> Dict[str, int]:
        """Transform log entries into error count report."""
        for entry in entries:
            if entry.level == "ERROR":
                self._aggregate_error(entry.message)
            elif entry.level == "INFO":
                self._process_info(entry)

        return self._error_counts.copy()

    def _aggregate_error(self, message: str) -> None:
        """Aggregate error messages by counting occurrences."""
        self._error_counts[message] = self._error_counts.get(message, 0) + 1

    def _process_info(self, entry: LogEntry) -> None:
        """Process INFO level entries for user actions."""
        match = self.USER_PATTERN.search(entry.message)
        if match:
            user_id = match.group(1)
            self._user_actions.append(
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "user": user_id,
                    "message": entry.message,
                }
            )


# =============================================================================
# Load
# =============================================================================


class ReportLoader:
    """Loads transformed data into an HTML report."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def load(self, error_counts: Dict[str, int]) -> Path:
        """Generate and save the HTML report."""
        html = self._generate_html(error_counts)
        self._config.report_file.write_text(html)
        return self._config.report_file

    def _generate_html(self, error_counts: Dict[str, int]) -> str:
        """Generate HTML content from error counts."""
        items = ""
        for message, count in error_counts.items():
            items += f"<li>{message}: {count}</li>"

        return f"<html><body><h1>Report</h1><ul>{items}</ul></body></html>"


class DatabaseLoader:
    """Simulates loading data into a database."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def connect(self) -> None:
        """Simulate database connection."""
        print(f"Connecting to {self._config.db_host} as {self._config.db_user}...")


# =============================================================================
# ETL Pipeline
# =============================================================================


class ETLPipeline:
    """Orchestrates the Extract-Transform-Load process."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._extractor = LogExtractor(config.log_file)
        self._transformer = LogTransformer()
        self._db_loader = DatabaseLoader(config)
        self._report_loader = ReportLoader(config)

    def run(self) -> Path:
        """Execute the full ETL pipeline."""
        # Extract
        entries = self._extractor.extract()

        # Simulate DB connection
        self._db_loader.connect()

        # Transform
        error_counts = self._transformer.transform(entries)

        # Load
        report_path = self._report_loader.load(error_counts)

        print("Done.")
        return report_path


# =============================================================================
# Main
# =============================================================================


def create_dummy_log_file(log_file: Path) -> None:
    """Create a dummy log file for testing if it doesn't exist."""
    if log_file.exists():
        return

    log_file.write_text(
        "2023-10-01 10:00:00 INFO User 123 logged in\n"
        "2023-10-01 10:05:00 ERROR Connection failed\n"
        "2023-10-01 10:10:00 ERROR Connection failed\n"
    )


def main() -> int:
    """Main entry point."""
    config = Config()

    # Create dummy log file if not exists for testing
    create_dummy_log_file(config.log_file)

    # Run ETL pipeline
    pipeline = ETLPipeline(config)
    pipeline.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
