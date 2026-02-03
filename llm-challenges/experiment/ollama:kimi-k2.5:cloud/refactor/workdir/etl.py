"""
ETL Pipeline for processing server logs and generating HTML reports.

Follows the ETL pattern:
- Extract: Read and parse log files
- Transform: Process and aggregate data
- Load: Generate HTML report
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Protocol

# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class ETLConfig:
    """Configuration for the ETL pipeline."""

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: Path = Path("server.log")
    report_file: Path = Path("report.html")


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class LogEntry:
    """Represents a parsed log entry."""

    timestamp: datetime
    level: str
    message: str


@dataclass(frozen=True)
class UserAction:
    """Represents a user action extracted from a log entry."""

    timestamp: datetime
    user_id: str
    action: str


@dataclass(frozen=True)
class ErrorReport:
    """Aggregated error data for reporting."""

    error_counts: Dict[str, int]


# =============================================================================
# Extract Phase
# =============================================================================


class LogExtractor:
    """Extracts and parses log entries from files."""

    # Regex pattern for log lines: YYYY-MM-DD HH:MM:SS LEVEL message...
    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"  # Timestamp
        r"\s+(\w+)"  # Log level
        r"\s+(.*)$"  # Message
    )

    def __init__(self, config: ETLConfig) -> None:
        self.config = config

    def extract(self) -> List[LogEntry]:
        """Extract log entries from the configured log file."""
        entries: List[LogEntry] = []
        log_path = self.config.log_file

        if not log_path.exists():
            return entries

        content = log_path.read_text(encoding="utf-8")

        for line in content.strip().split("\n"):
            entry = self._parse_line(line)
            if entry:
                entries.append(entry)

        return entries

    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line using regex."""
        match = self.LOG_PATTERN.match(line.strip())
        if not match:
            return None

        timestamp_str, level, message = match.groups()

        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

        return LogEntry(
            timestamp=timestamp, level=level.upper(), message=message.strip()
        )


# =============================================================================
# Transform Phase
# =============================================================================


class LogTransformer:
    """Transforms extracted log entries into reportable data."""

    # Regex pattern to extract user ID from messages like "User 123 logged in"
    USER_ACTION_PATTERN = re.compile(r"User\s+(\d+)\s+(.*)", re.IGNORECASE)

    def transform(self, entries: List[LogEntry]) -> ErrorReport:
        """
        Transform log entries into an error report.

        Aggregates ERROR level messages and counts occurrences.
        """
        error_counts: Dict[str, int] = {}

        for entry in entries:
            if entry.level == "ERROR":
                error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

        return ErrorReport(error_counts=error_counts)

    def extract_user_actions(self, entries: List[LogEntry]) -> List[UserAction]:
        """Extract user actions from INFO level log entries."""
        actions: List[UserAction] = []

        for entry in entries:
            if entry.level == "INFO":
                match = self.USER_ACTION_PATTERN.search(entry.message)
                if match:
                    user_id, action_desc = match.groups()
                    actions.append(
                        UserAction(
                            timestamp=entry.timestamp,
                            user_id=user_id,
                            action=action_desc.strip(),
                        )
                    )

        return actions


# =============================================================================
# Load Phase
# =============================================================================


class ReportLoader:
    """Loads transformed data into output formats."""

    def __init__(self, config: ETLConfig) -> None:
        self.config = config

    def load(self, report: ErrorReport) -> Path:
        """Generate and save the HTML report."""
        html_content = self._generate_html(report)
        self.config.report_file.write_text(html_content, encoding="utf-8")
        return self.config.report_file

    def _generate_html(self, report: ErrorReport) -> str:
        """Generate HTML content from the error report."""
        lines: List[str] = ["<html><body><h1>Report</h1><ul>"]

        for message, count in report.error_counts.items():
            lines.append(f"<li>{message}: {count}</li>")

        lines.append("</ul></body></html>")

        return "".join(lines)

    def simulate_db_load(self, entries: List[LogEntry]) -> None:
        """Simulate loading data into a database."""
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")


# =============================================================================
# ETL Pipeline Orchestrator
# =============================================================================


class ETLPipeline:
    """Orchestrates the ETL process."""

    def __init__(
        self,
        config: Optional[ETLConfig] = None,
        extractor: Optional[LogExtractor] = None,
        transformer: Optional[LogTransformer] = None,
        loader: Optional[ReportLoader] = None,
    ) -> None:
        self.config = config or ETLConfig()
        self.extractor = extractor or LogExtractor(self.config)
        self.transformer = transformer or LogTransformer()
        self.loader = loader or ReportLoader(self.config)

    def run(self) -> Path:
        """Execute the complete ETL pipeline."""
        # Extract
        entries = self.extractor.extract()

        # Simulate database load (as in original)
        self.loader.simulate_db_load(entries)

        # Transform
        report = self.transformer.transform(entries)

        # Load
        report_path = self.loader.load(report)

        print("Done.")
        return report_path


# =============================================================================
# Main Entry Point
# =============================================================================


def create_sample_log_file(config: ETLConfig) -> None:
    """Create a dummy log file for testing if it doesn't exist."""
    if not config.log_file.exists():
        sample_data = """\
2023-10-01 10:00:00 INFO User 123 logged in
2023-10-01 10:05:00 ERROR Connection failed
2023-10-01 10:10:00 ERROR Connection failed
"""
        config.log_file.write_text(sample_data, encoding="utf-8")


def main() -> None:
    """Main entry point for the ETL pipeline."""
    config = ETLConfig()

    # Create sample log file if not exists for testing
    create_sample_log_file(config)

    # Run the pipeline
    pipeline = ETLPipeline(config=config)
    pipeline.run()


if __name__ == "__main__":
    main()
