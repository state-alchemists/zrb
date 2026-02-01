#!/usr/bin/env python3
"""
ETL (Extract, Transform, Load) pipeline for processing server logs.

Refactored version with:
- Proper ETL pattern separation
- Configuration management
- Regex-based parsing
- Type hints
- Maintainable structure
"""

import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

# ============================================================================
# Configuration
# ============================================================================


@dataclass
class Config:
    """Configuration for the ETL pipeline."""

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    output_file: str = "report.html"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, filepath: str) -> "Config":
        """Load config from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)


# ============================================================================
# Data Models
# ============================================================================


class LogEntry(TypedDict):
    """Represents a parsed log entry."""

    timestamp: str
    log_type: str
    message: str
    metadata: Dict[str, Any]


class ProcessedEntry(TypedDict):
    """Represents a processed log entry after transformation."""

    date: str
    type: str
    msg: Optional[str]
    user: Optional[str]


# ============================================================================
# Extract Phase
# ============================================================================


class LogExtractor:
    """Handles extraction of log data from files."""

    # Regex patterns for log parsing
    LOG_PATTERN = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
        r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
        r"(?P<type>\w+)\s+"
        r"(?P<message>.+)$"
    )

    USER_PATTERN = re.compile(r"User\s+(?P<user_id>\d+)")

    def __init__(self, config: Config):
        self.config = config

    def extract(self) -> List[LogEntry]:
        """
        Extract log entries from the log file.

        Returns:
            List of parsed log entries
        """
        log_entries: List[LogEntry] = []
        log_path = Path(self.config.log_file)

        if not log_path.exists():
            print(f"Warning: Log file '{self.config.log_file}' not found.")
            return log_entries

        with open(log_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                entry = self._parse_log_line(line, line_num)
                if entry:
                    log_entries.append(entry)

        print(f"Extracted {len(log_entries)} log entries.")
        return log_entries

    def _parse_log_line(self, line: str, line_num: int) -> Optional[LogEntry]:
        """
        Parse a single log line using regex.

        Args:
            line: The log line to parse
            line_num: Line number for error reporting

        Returns:
            Parsed log entry or None if parsing fails
        """
        match = self.LOG_PATTERN.match(line)
        if not match:
            print(f"Warning: Could not parse line {line_num}: {line[:50]}...")
            return None

        groups = match.groupdict()
        timestamp = f"{groups['date']} {groups['time']}"
        log_type = groups["type"]
        message = groups["message"]

        # Extract metadata based on log type
        metadata: Dict[str, Any] = {}

        if log_type == "INFO":
            user_match = self.USER_PATTERN.search(message)
            if user_match:
                metadata["user_id"] = user_match.group("user_id")

        return LogEntry(
            timestamp=timestamp, log_type=log_type, message=message, metadata=metadata
        )


# ============================================================================
# Transform Phase
# ============================================================================


class LogTransformer:
    """Handles transformation of log data."""

    def transform(self, log_entries: List[LogEntry]) -> List[ProcessedEntry]:
        """
        Transform raw log entries into processed entries.

        Args:
            log_entries: Raw log entries from extract phase

        Returns:
            List of processed entries
        """
        processed_entries: List[ProcessedEntry] = []

        for entry in log_entries:
            processed = self._transform_entry(entry)
            if processed:
                processed_entries.append(processed)

        print(f"Transformed {len(processed_entries)} entries.")
        return processed_entries

    def _transform_entry(self, entry: LogEntry) -> Optional[ProcessedEntry]:
        """
        Transform a single log entry.

        Args:
            entry: Raw log entry

        Returns:
            Processed entry or None if entry should be filtered out
        """
        log_type = entry["log_type"]
        message = entry["message"]

        if log_type == "ERROR":
            return ProcessedEntry(
                date=entry["timestamp"], type="ERROR", msg=message, user=None
            )
        elif log_type == "INFO" and "User" in message:
            user_id = entry["metadata"].get("user_id")
            if user_id:
                return ProcessedEntry(
                    date=entry["timestamp"], type="USER_ACTION", msg=None, user=user_id
                )

        return None


# ============================================================================
# Load Phase
# ============================================================================


class ReportGenerator:
    """Handles generation of HTML reports from processed data."""

    def __init__(self, config: Config):
        self.config = config

    def generate_report(self, processed_entries: List[ProcessedEntry]) -> str:
        """
        Generate HTML report from processed entries.

        Args:
            processed_entries: Processed log entries

        Returns:
            HTML report as string
        """
        # Count error occurrences
        error_counts: Dict[str, int] = {}
        for entry in processed_entries:
            if entry["type"] == "ERROR" and entry["msg"]:
                error_msg = entry["msg"]
                error_counts[error_msg] = error_counts.get(error_msg, 0) + 1

        # Generate HTML matching the original format exactly
        html = "<html><body><h1>Report</h1><ul>"
        for error_msg, count in sorted(error_counts.items()):
            html += f"<li>{error_msg}: {count}</li>"
        html += "</ul></body></html>"

        return html

    def save_report(self, html_content: str) -> None:
        """
        Save HTML report to file.

        Args:
            html_content: HTML content to save
        """
        output_path = Path(self.config.output_file)
        with open(output_path, "w") as f:
            f.write(html_content)
        print(f"Report saved to '{self.config.output_file}'.")


class DatabaseLoader:
    """Handles loading data to database (simulated)."""

    def __init__(self, config: Config):
        self.config = config

    def load(self, processed_entries: List[ProcessedEntry]) -> None:
        """
        Simulate loading data to database.

        Args:
            processed_entries: Processed entries to load
        """
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")
        print(f"Would load {len(processed_entries)} entries to database.")
        # In a real implementation, this would connect to a database
        # and insert/update records


# ============================================================================
# ETL Pipeline
# ============================================================================


class ETLPipeline:
    """Main ETL pipeline orchestrator."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.extractor = LogExtractor(self.config)
        self.transformer = LogTransformer()
        self.db_loader = DatabaseLoader(self.config)
        self.report_generator = ReportGenerator(self.config)

    def run(self) -> None:
        """Execute the complete ETL pipeline."""
        print("Starting ETL pipeline...")

        # Extract
        print("\n=== Extract Phase ===")
        log_entries = self.extractor.extract()

        # Transform
        print("\n=== Transform Phase ===")
        processed_entries = self.transformer.transform(log_entries)

        # Load
        print("\n=== Load Phase ===")
        self.db_loader.load(processed_entries)

        # Generate report
        print("\n=== Report Generation ===")
        html_report = self.report_generator.generate_report(processed_entries)
        self.report_generator.save_report(html_report)

        print("\nETL pipeline completed successfully.")


# ============================================================================
# Main Execution
# ============================================================================


def create_sample_log_file(log_file: str = "server.log") -> None:
    """Create a sample log file for testing if it doesn't exist."""
    log_path = Path(log_file)
    if not log_path.exists():
        sample_logs = [
            "2023-10-01 10:00:00 INFO User 123 logged in",
            "2023-10-01 10:05:00 ERROR Connection failed",
            "2023-10-01 10:10:00 ERROR Connection failed",
        ]

        with open(log_path, "w") as f:
            f.write("\n".join(sample_logs))


def main() -> None:
    """Main entry point."""
    # Create sample log if needed
    create_sample_log_file()

    # Run ETL pipeline
    pipeline = ETLPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
