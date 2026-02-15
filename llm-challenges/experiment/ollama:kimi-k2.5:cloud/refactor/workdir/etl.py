"""
Log Processing ETL Pipeline

Extracts error and user events from log files, transforms into structured data,
and loads into a report.html summary.

Environment Variables:
    DB_HOST: Database hostname (default: localhost)
    DB_USER: Database username (default: admin)
    DB_PASS: Database password (default: admin)
    LOG_FILE: Path to log file (default: server.log)
"""

import datetime
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Protocol


# =============================================================================
# Configuration
# =============================================================================

@dataclass(frozen=True)
class Config:
    """Application configuration from environment variables."""
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "admin"))
    db_pass: str = field(default_factory=lambda: os.getenv("DB_PASS", "admin"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "server.log"))


# =============================================================================
# Data Models
# =============================================================================

@dataclass(frozen=True)
class LogEntry:
    """Represents a single parsed log entry."""
    timestamp: str
    level: str
    message: str
    user_id: str | None = None


@dataclass
class ErrorReport:
    """Aggregated error statistics."""
    errors: Dict[str, int] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Increment count for an error message."""
        self.errors[message] = self.errors.get(message, 0) + 1


# =============================================================================
# ETL Components
# =============================================================================

class Extractor(ABC):
    """Abstract base for data extraction."""

    @abstractmethod
    def extract(self) -> List[LogEntry]:
        """Extract data and return list of log entries."""
        raise NotImplementedError


class Transformer(ABC):
    """Abstract base for data transformation."""

    @abstractmethod
    def transform(self, entries: List[LogEntry]) -> ErrorReport:
        """Transform entries into aggregated report."""
        raise NotImplementedError


class Loader(ABC):
    """Abstract base for data loading."""

    @abstractmethod
    def load(self, report: ErrorReport) -> None:
        """Load report to output destination."""
        raise NotImplementedError


# =============================================================================
# Concrete Implementations
# =============================================================================

class LogFileExtractor(Extractor):
    """Extracts log entries from a file using regex parsing."""

    # Regex pattern: TIMESTAMP LEVEL [optional prefix] MESSAGE
    # Handles variable whitespace and extracts user IDs from INFO logs
    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(ERROR|INFO|WARN|DEBUG)\s+(.*)$"
    )
    USER_PATTERN = re.compile(r"User\s+(\d+)\s+logged\s+(in|out)")

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)

    def extract(self) -> List[LogEntry]:
        """Parse log file and return structured entries."""
        entries: List[LogEntry] = []

        if not self.file_path.exists():
            return entries

        with self.file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                entry = self._parse_line(line)
                if entry:
                    entries.append(entry)

        return entries

    def _parse_line(self, line: str) -> LogEntry | None:
        """Parse a single log line into a LogEntry."""
        match = self.LOG_PATTERN.match(line)
        if not match:
            return None

        timestamp, level, message = match.groups()
        user_id = None

        # Extract user ID from login/logout messages
        if level == "INFO":
            user_match = self.USER_PATTERN.search(message)
            if user_match:
                user_id = user_match.group(1)

        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            user_id=user_id
        )


class ErrorAggregator(Transformer):
    """Aggregates error entries into a summary report."""

    def transform(self, entries: List[LogEntry]) -> ErrorReport:
        """Count occurrences of each unique error message."""
        report = ErrorReport()

        for entry in entries:
            if entry.level == "ERROR":
                report.add_error(entry.message)

        return report


class HtmlReportLoader(Loader):
    """Generates an HTML report file."""

    def __init__(self, output_path: str = "report.html") -> None:
        self.output_path = Path(output_path)

    def load(self, report: ErrorReport) -> None:
        """Generate HTML report from error statistics."""
        html_content = self._generate_html(report)
        self.output_path.write_text(html_content, encoding="utf-8")

    def _generate_html(self, report: ErrorReport) -> str:
        """Build HTML document with error summary."""
        lines = [
            "<html>",
            "<head><title>System Report</title></head>",
            "<body>",
            "<h1>Error Summary</h1>",
            "<ul>"
        ]

        for err_msg, count in report.errors.items():
            escaped_msg = self._escape_html(err_msg)
            lines.append(f"<li><b>{escaped_msg}</b>: {count} occurrences</li>")

        lines.extend([
            "</ul>",
            "</body>",
            "</html>"
        ])

        return "\n".join(lines)

    @staticmethod
    def _escape_html(text: str) -> str:
        """Basic HTML escaping for safety."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


class DatabaseLoader(Loader):
    """Simulates database loading (for future implementation)."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def load(self, report: ErrorReport) -> None:
        """Simulate database connection and data loading."""
        # NOTE: Actual DB insertion logic removed by previous dev
        # This serves as a placeholder for future database integration
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")
        print(f"Would insert {len(report.errors)} unique error types")


# =============================================================================
# ETL Pipeline
# =============================================================================

class ETLPipeline:
    """Orchestrates the ETL process."""

    def __init__(
        self,
        extractor: Extractor,
        transformer: Transformer,
        loaders: List[Loader]
    ) -> None:
        self.extractor = extractor
        self.transformer = transformer
        self.loaders = loaders

    def run(self) -> None:
        """Execute the full ETL pipeline."""
        # Extract
        entries = self.extractor.extract()
        print(f"Extracted {len(entries)} log entries")

        # Transform
        report = self.transformer.transform(entries)
        print(f"Transformed into {len(report.errors)} unique errors")

        # Load
        for loader in self.loaders:
            loader.load(report)
        print(f"Job finished at {datetime.datetime.now()}")


# =============================================================================
# Setup & Utilities
# =============================================================================

def create_sample_log(file_path: str) -> None:
    """Create sample log data for testing."""
    sample_data = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    Path(file_path).write_text("\n".join(sample_data) + "\n", encoding="utf-8")


def main() -> int:
    """Main entry point."""
    config = Config()

    # Create sample data if log file doesn't exist
    if not Path(config.log_file).exists():
        create_sample_log(config.log_file)
        print(f"Created sample log file: {config.log_file}")

    # Build pipeline
    pipeline = ETLPipeline(
        extractor=LogFileExtractor(config.log_file),
        transformer=ErrorAggregator(),
        loaders=[
            HtmlReportLoader("report.html"),
            DatabaseLoader(config),
        ]
    )

    pipeline.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
