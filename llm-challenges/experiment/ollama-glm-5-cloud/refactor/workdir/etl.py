"""
ETL Pipeline for Server Log Analysis.

This module implements an Extract-Transform-Load pattern for processing
server logs and generating error reports.

Configuration:
    DB_HOST: Database host (default: localhost)
    DB_USER: Database user (default: admin)
    DB_PASS: Database password (default: password123)
    LOG_FILE: Path to log file (default: server.log)
"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class LogEntryType(Enum):
    """Type of log entry extracted from server logs."""
    ERROR = "ERR"
    USER = "USR"


@dataclass
class Config:
    """Configuration loaded from environment variables.
    
    Environment variables can be set to override defaults.
    For production, use environment variables instead of hardcoding.
    """
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "admin"))
    db_pass: str = field(default_factory=lambda: os.getenv("DB_PASS", "password123"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "server.log"))

    @classmethod
    def from_env(cls) -> Config:
        """Create config from environment variables."""
        return cls()


@dataclass
class LogEntry:
    """Represents a single parsed log entry."""
    timestamp: str
    entry_type: LogEntryType
    message: str = ""
    user_id: str | None = None


@dataclass
class ErrorSummary:
    """Aggregated error statistics for report generation."""
    counts: dict[str, int] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Record an error occurrence."""
        self.counts[message] = self.counts.get(message, 0) + 1


# Regex patterns for robust log parsing
# Format: "YYYY-MM-DD HH:MM:SS LEVEL [rest of message]"
_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|ERROR|WARN|DEBUG)\s+"
    r"(?P<message>.+)$"
)
# User extraction: finds "User <id>" pattern
_USER_PATTERN = re.compile(r"User\s+(\S+)")


class Extractor:
    """Extracts raw log lines from file source."""

    def __init__(self, config: Config):
        self._config = config

    def extract_lines(self) -> Iterator[str]:
        """Yield non-empty lines from the log file.
        
        Yields:
            Iterator of log lines (stripped).
        
        Raises:
            FileNotFoundError: If log file doesn't exist.
        """
        log_path = self._config.log_file
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"Log file not found: {log_path}")
        
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line


class Transformer:
    """Transforms raw log lines into structured LogEntry objects."""

    def transform(self, lines: Iterator[str]) -> list[LogEntry]:
        """Parse log lines into structured entries.
        
        Args:
            lines: Iterator of raw log lines.
        
        Returns:
            List of parsed LogEntry objects.
        """
        entries: list[LogEntry] = []
        
        for line in lines:
            entry = self._parse_line(line)
            if entry is not None:
                entries.append(entry)
        
        return entries

    def _parse_line(self, line: str) -> LogEntry | None:
        """Parse a single log line into a LogEntry.
        
        Uses regex for robust parsing that handles:
        - Multiple spaces between fields
        - Variable message lengths
        
        Args:
            line: Raw log line string.
        
        Returns:
            LogEntry if line is parseable, None otherwise.
        """
        match = _LOG_PATTERN.match(line)
        if not match:
            return None
        
        timestamp = match.group("timestamp")
        level = match.group("level")
        message = match.group("message")

        if level == "ERROR":
            return LogEntry(
                timestamp=timestamp,
                entry_type=LogEntryType.ERROR,
                message=message,
            )
        
        if level == "INFO":
            # Check for user activity
            user_match = _USER_PATTERN.search(message)
            if user_match:
                return LogEntry(
                    timestamp=timestamp,
                    entry_type=LogEntryType.USER,
                    user_id=user_match.group(1),
                )
        
        return None


class Loader:
    """Loads processed data to destination (report file)."""

    def __init__(self, config: Config):
        self._config = config

    def generate_report(self, entries: list[LogEntry], output_path: str = "report.html") -> None:
        """Generate HTML error summary report.
        
        Args:
            entries: List of processed log entries.
            output_path: Path to output HTML file.
        """
        summary = self._aggregate_errors(entries)
        html = self._build_html(summary)
        
        with open(output_path, "w") as f:
            f.write(html)

    def _aggregate_errors(self, entries: list[LogEntry]) -> ErrorSummary:
        """Aggregate error counts from entries."""
        summary = ErrorSummary()
        
        for entry in entries:
            if entry.entry_type == LogEntryType.ERROR:
                summary.add_error(entry.message)
        
        return summary

    def _build_html(self, summary: ErrorSummary) -> str:
        """Build HTML report content.
        
        Maintains exact output format for compatibility.
        """
        lines = [
            "<html>",
            "<head><title>System Report</title></head>",
            "<body>",
            "<h1>Error Summary</h1>",
            "<ul>",
        ]
        
        for err_msg, count in summary.counts.items():
            lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
        
        lines.extend([
            "</ul>",
            "</body>",
            "</html>",
        ])
        
        return "\n".join(lines) + "\n"


class ETLPipeline:
    """Coordinates the ETL process: Extract -> Transform -> Load."""

    def __init__(self, config: Config):
        self._config = config
        self._extractor = Extractor(config)
        self._transformer = Transformer()
        self._loader = Loader(config)

    def run(self, report_path: str = "report.html") -> None:
        """Execute the full ETL pipeline.
        
        Args:
            report_path: Output path for the report file.
        """
        # Log start
        print(f"Connecting to {self._config.db_host} as {self._config.db_user}...")
        
        # Extract: read log lines
        lines = self._extractor.extract_lines()
        
        # Transform: parse into structured entries
        entries = self._transformer.transform(lines)
        
        # Load: generate report
        self._loader.generate_report(entries, report_path)
        
        # Log completion
        print(f"Job finished at {datetime.datetime.now()}")


def create_sample_log(log_path: str) -> None:
    """Create sample log file for testing/demo purposes."""
    sample_entries = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    
    with open(log_path, "w") as f:
        for entry in sample_entries:
            f.write(entry + "\n")


def main() -> None:
    """Entry point for the ETL pipeline."""
    config = Config.from_env()
    
    # Setup sample data if log file doesn't exist
    if not os.path.exists(config.log_file):
        print(f"Creating sample log file: {config.log_file}")
        create_sample_log(config.log_file)
    
    pipeline = ETLPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()