#!/usr/bin/env python3
"""
Refactored ETL pipeline for log processing.
Follows proper ETL pattern with separation of concerns.
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_user=os.getenv("DB_USER", "admin"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            output_file=os.getenv("OUTPUT_FILE", "report.html"),
        )


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class LogEntry:
    """Represents a parsed log entry."""

    timestamp: datetime
    level: str  # "INFO", "ERROR", etc.
    message: str
    raw_line: str

    @property
    def is_error(self) -> bool:
        return self.level == "ERROR"

    @property
    def is_info(self) -> bool:
        return self.level == "INFO"


@dataclass
class ProcessedEntry:
    """Represents a processed log entry with extracted information."""

    timestamp: datetime
    entry_type: str  # "ERROR", "USER_ACTION", etc.
    data: Dict[str, Any]


# ============================================================================
# Extract Layer
# ============================================================================


class LogExtractor:
    """Handles extraction of log data from files."""

    def __init__(self, config: Config):
        self.config = config

    def extract(self) -> List[str]:
        """Extract raw log lines from the log file."""
        log_path = Path(self.config.log_file)

        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {self.config.log_file}")

        with open(log_path, "r") as f:
            return [line.strip() for line in f.readlines() if line.strip()]


# ============================================================================
# Transform Layer
# ============================================================================


class LogTransformer:
    """Handles transformation of raw log data into structured format."""

    # Regex patterns for parsing log lines
    LOG_PATTERN = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"  # Date: YYYY-MM-DD
        r"(?P<time>\d{2}:\d{2}:\d{2})\s+"  # Time: HH:MM:SS
        r"(?P<level>\w+)\s+"  # Level: INFO, ERROR, etc.
        r"(?P<message>.*)"  # Message: rest of the line
    )

    USER_PATTERN = re.compile(r"User\s+(?P<user_id>\d+)")

    def __init__(self):
        pass

    def parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line into a LogEntry object."""
        match = self.LOG_PATTERN.match(line)
        if not match:
            return None

        try:
            timestamp_str = f"{match.group('date')} {match.group('time')}"
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

            return LogEntry(
                timestamp=timestamp,
                level=match.group("level"),
                message=match.group("message"),
                raw_line=line,
            )
        except (ValueError, KeyError):
            return None

    def transform(self, raw_lines: List[str]) -> List[ProcessedEntry]:
        """Transform raw log lines into processed entries."""
        processed_entries: List[ProcessedEntry] = []

        for line in raw_lines:
            log_entry = self.parse_log_line(line)
            if not log_entry:
                continue

            if log_entry.is_error:
                processed_entries.append(
                    ProcessedEntry(
                        timestamp=log_entry.timestamp,
                        entry_type="ERROR",
                        data={"message": log_entry.message},
                    )
                )

            elif log_entry.is_info:
                # Check for user actions
                user_match = self.USER_PATTERN.search(log_entry.message)
                if user_match:
                    processed_entries.append(
                        ProcessedEntry(
                            timestamp=log_entry.timestamp,
                            entry_type="USER_ACTION",
                            data={"user_id": user_match.group("user_id")},
                        )
                    )

        return processed_entries


# ============================================================================
# Load Layer
# ============================================================================


class ReportGenerator:
    """Handles generation of reports from processed data."""

    def __init__(self, config: Config):
        self.config = config

    def generate_error_report(
        self, processed_entries: List[ProcessedEntry]
    ) -> Dict[str, int]:
        """Generate error frequency report."""
        error_counts: Dict[str, int] = {}

        for entry in processed_entries:
            if entry.entry_type == "ERROR":
                error_msg = entry.data.get("message", "Unknown error")
                error_counts[error_msg] = error_counts.get(error_msg, 0) + 1

        return error_counts

    def generate_html_report(self, error_counts: Dict[str, int]) -> str:
        """Generate HTML report from error counts."""
        # Match the exact format of the original report
        html = "<html><body><h1>Report</h1><ul>"

        for error_msg, count in sorted(error_counts.items()):
            html += f"<li>{error_msg}: {count}</li>"

        html += "</ul></body></html>"

        return html

    def save_report(self, html_content: str) -> None:
        """Save HTML report to file."""
        with open(self.config.output_file, "w") as f:
            f.write(html_content)


class DatabaseSimulator:
    """Simulates database operations."""

    def __init__(self, config: Config):
        self.config = config

    def connect(self) -> None:
        """Simulate database connection."""
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")

    def insert_entries(self, entries: List[ProcessedEntry]) -> None:
        """Simulate inserting entries into database."""
        # In a real implementation, this would insert into a database
        print(f"Would insert {len(entries)} entries into database")


# ============================================================================
# ETL Pipeline
# ============================================================================


class ETLPipeline:
    """Main ETL pipeline orchestrator."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.extractor = LogExtractor(self.config)
        self.transformer = LogTransformer()
        self.report_generator = ReportGenerator(self.config)
        self.db_simulator = DatabaseSimulator(self.config)

    def run(self) -> None:
        """Execute the complete ETL pipeline."""
        print("Starting ETL pipeline...")

        # Extract
        print("Extracting log data...")
        raw_lines = self.extractor.extract()
        print(f"Extracted {len(raw_lines)} log lines")

        # Transform
        print("Transforming log data...")
        processed_entries = self.transformer.transform(raw_lines)
        print(f"Processed {len(processed_entries)} entries")

        # Load (simulated database)
        print("Loading data to database...")
        self.db_simulator.connect()
        self.db_simulator.insert_entries(processed_entries)

        # Generate report
        print("Generating report...")
        error_counts = self.report_generator.generate_error_report(processed_entries)
        html_report = self.report_generator.generate_html_report(error_counts)
        self.report_generator.save_report(html_report)

        print(f"Report saved to {self.config.output_file}")
        print("ETL pipeline completed successfully!")


# ============================================================================
# Main Execution
# ============================================================================


def create_sample_log_file(log_file: str = "server.log") -> None:
    """Create a sample log file for testing if it doesn't exist."""
    if not os.path.exists(log_file):
        sample_logs = [
            "2023-10-01 10:00:00 INFO User 123 logged in",
            "2023-10-01 10:05:00 ERROR Connection failed",
            "2023-10-01 10:10:00 ERROR Connection failed",
        ]

        with open(log_file, "w") as f:
            f.write("\n".join(sample_logs))

        print(f"Created sample log file: {log_file}")


def main() -> None:
    """Main entry point."""
    # Create sample log file if needed
    create_sample_log_file()

    # Run ETL pipeline
    config = Config.from_env()
    pipeline = ETLPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
