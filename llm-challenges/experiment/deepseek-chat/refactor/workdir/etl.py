#!/usr/bin/env python3
"""
ETL Pipeline for Log Analysis

Refactored monolithic script into modular ETL pattern:
- Extract: Parse log files with regex
- Transform: Process and categorize log entries
- Load: Generate HTML report

Maintains backward compatibility with original output.
"""

import datetime
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# Configuration
# ============================================================================


@dataclass
class Config:
    """Configuration for the ETL pipeline"""

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    report_file: str = "report.html"

    @classmethod
    def load(cls, config_file: Optional[str] = None) -> "Config":
        """Load configuration from file or use defaults"""
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                print(f"Warning: Could not load config from {config_file}: {e}")

        return cls()


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class LogEntry:
    """Parsed log entry"""

    timestamp: datetime.datetime
    log_type: str
    message: str


@dataclass
class ProcessedEntry:
    """Processed log entry"""

    entry_type: str  # "ERROR" or "USER_ACTION"
    message: Optional[str] = None
    user_id: Optional[str] = None


# ============================================================================
# Extract Layer
# ============================================================================


class LogExtractor:
    """Extract log entries from files"""

    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.+)$"
    )

    @classmethod
    def extract(cls, log_file: str) -> List[LogEntry]:
        """Extract and parse log entries"""
        entries = []

        if not os.path.exists(log_file):
            return entries

        with open(log_file, "r") as f:
            for line in f:
                entry = cls._parse_line(line.strip())
                if entry:
                    entries.append(entry)

        return entries

    @classmethod
    def _parse_line(cls, line: str) -> Optional[LogEntry]:
        """Parse a single log line"""
        match = cls.LOG_PATTERN.match(line)
        if not match:
            return None

        date_str, time_str, log_type, message = match.groups()

        try:
            timestamp = datetime.datetime.strptime(
                f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"
            )
            return LogEntry(timestamp, log_type, message.strip())
        except ValueError:
            return None


# ============================================================================
# Transform Layer
# ============================================================================


class LogTransformer:
    """Transform log entries into processed data"""

    USER_PATTERN = re.compile(r"User\s+(\d+)")

    @classmethod
    def transform(cls, entries: List[LogEntry]) -> List[ProcessedEntry]:
        """Transform log entries"""
        processed = []

        for entry in entries:
            if entry.log_type == "ERROR":
                processed.append(
                    ProcessedEntry(entry_type="ERROR", message=entry.message)
                )
            elif entry.log_type == "INFO":
                user_match = cls.USER_PATTERN.search(entry.message)
                if user_match:
                    processed.append(
                        ProcessedEntry(
                            entry_type="USER_ACTION", user_id=user_match.group(1)
                        )
                    )

        return processed

    @classmethod
    def count_errors(cls, entries: List[ProcessedEntry]) -> Dict[str, int]:
        """Count error occurrences"""
        counts = {}
        for entry in entries:
            if entry.entry_type == "ERROR" and entry.message:
                counts[entry.message] = counts.get(entry.message, 0) + 1
        return counts


# ============================================================================
# Load Layer
# ============================================================================


class ReportGenerator:
    """Generate HTML reports"""

    @staticmethod
    def generate(error_counts: Dict[str, int], output_file: str) -> None:
        """Generate HTML report"""
        html_lines = ["<html><body><h1>Report</h1><ul>"]

        for message, count in error_counts.items():
            html_lines.append(f"<li>{message}: {count}</li>")

        html_lines.append("</ul></body></html>")

        with open(output_file, "w") as f:
            f.write("".join(html_lines))


# ============================================================================
# ETL Pipeline
# ============================================================================


class ETLPipeline:
    """Main ETL pipeline orchestrator"""

    def __init__(self, config: Config):
        self.config = config

    def run(self) -> None:
        """Execute the ETL pipeline"""
        # Extract
        entries = LogExtractor.extract(self.config.log_file)

        # Simulate DB connection (for backward compatibility)
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")

        # Transform
        processed = LogTransformer.transform(entries)
        error_counts = LogTransformer.count_errors(processed)

        # Load
        ReportGenerator.generate(error_counts, self.config.report_file)

        print("Done.")


# ============================================================================
# Main Function (Backward Compatible)
# ============================================================================


def main():
    """Main function matching original script's interface"""
    # Create sample log if needed
    if not os.path.exists("server.log"):
        with open("server.log", "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    # Run pipeline
    config = Config.load()
    pipeline = ETLPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
