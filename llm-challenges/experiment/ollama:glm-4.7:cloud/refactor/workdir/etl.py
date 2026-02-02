import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ============================================================================
# CONFIGURATION
# ============================================================================


@dataclass
class Config:
    """Configuration for the ETL process."""

    # Database configuration
    db_host: str = "localhost"
    db_user: str = "admin"

    # File paths
    log_file: str = "server.log"
    report_file: str = "report.html"

    # Parsing patterns
    error_pattern: str = r"^(\S+ \S+) ERROR (.+)$"
    user_action_pattern: str = r"^(\S+ \S+) INFO User (\d+) (.+)"

    # Report template
    report_template: str = """<html><body><h1>Report</h1><ul>
{report_items}
</ul></body></html>"""


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class LogEntry:
    """Represents a parsed log entry."""

    date: str
    type: str
    msg: str
    user_id: Optional[str] = None


@dataclass
class ReportData:
    """Represents the compiled report data."""

    error_counts: Dict[str, int] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        """Increment count for an error message."""
        self.error_counts[msg] = self.error_counts.get(msg, 0) + 1


# ============================================================================
# EXTRACT
# ============================================================================


class Extractor:
    """Handles extraction of data from log files."""

    def __init__(self, config: Config):
        self.config = config
        self.error_regex = re.compile(config.error_pattern)
        self.action_regex = re.compile(config.user_action_pattern)

    def extract_from_file(self, filepath: str) -> List[LogEntry]:
        """
        Extract log entries from a file.

        Args:
            filepath: Path to the log file

        Returns:
            List of parsed LogEntry objects
        """
        if not os.path.exists(filepath):
            return []

        entries = []
        with open(filepath, "r") as f:
            for line in f:
                entry = self._parse_line(line.strip())
                if entry:
                    entries.append(entry)

        return entries

    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """
        Parse a single log line using regex.

        Args:
            line: Raw log line

        Returns:
            LogEntry if line matches a known pattern, None otherwise
        """
        # Try ERROR pattern
        error_match = self.error_regex.match(line)
        if error_match:
            return LogEntry(
                date=error_match.group(1), type="ERROR", msg=error_match.group(2)
            )

        # Try user action pattern
        action_match = self.action_regex.match(line)
        if action_match:
            return LogEntry(
                date=action_match.group(1),
                type="USER_ACTION",
                msg=action_match.group(3),
                user_id=action_match.group(2),
            )

        return None


# ============================================================================
# TRANSFORM
# ============================================================================


class Transformer:
    """Handles transformation of extracted data."""

    def transform_to_report(self, entries: List[LogEntry]) -> ReportData:
        """
        Transform log entries into report data.

        Args:
            entries: List of LogEntry objects

        Returns:
            ReportData object with aggregated statistics
        """
        report = ReportData()

        for entry in entries:
            if entry.type == "ERROR":
                report.add_error(entry.msg)

        return report


# ============================================================================
# LOAD
# ============================================================================


class Loader:
    """Handles loading of data to various outputs."""

    def __init__(self, config: Config):
        self.config = config

    def simulate_database_connection(self) -> None:
        """Simulates connecting to a database."""
        print(f"Connecting to {self.config.db_host} " f"as {self.config.db_user}...")

    def generate_html_report(self, report: ReportData) -> str:
        """
        Generate HTML report from report data.

        Args:
            report: ReportData object

        Returns:
            HTML string
        """
        report_items = ""
        for msg, count in report.error_counts.items():
            report_items += f"<li>{msg}: {count}</li>"

        return self.config.report_template.format(report_items=report_items)

    def save_html_report(self, html: str, filepath: str) -> None:
        """
        Save HTML report to file.

        Args:
            html: HTML content
            filepath: Output file path
        """
        with open(filepath, "w") as f:
            f.write(html)
        print(f"Report saved to {filepath}")


# ============================================================================
# ETL ORCHESTRATOR
# ============================================================================


class ETLPipeline:
    """Orchestrates the ETL process."""

    def __init__(self, config: Config):
        self.config = config
        self.extractor = Extractor(config)
        self.transformer = Transformer()
        self.loader = Loader(config)

    def run(self) -> None:
        """
        Execute the complete ETL pipeline.

        1. Extract log entries from file
        2. Transform entries into report data
        3. Load/save the report
        """
        # Extract
        entries = self.extractor.extract_from_file(self.config.log_file)
        print(f"Extracted {len(entries)} log entries")

        # Transform
        report = self.transformer.transform_to_report(entries)
        print(f"Found {len(report.error_counts)} unique error messages")

        # Load
        self.loader.simulate_database_connection()
        html = self.loader.generate_html_report(report)
        self.loader.save_html_report(html, self.config.report_file)

        print("Done.")


# ============================================================================
# MAIN
# ============================================================================


def ensure_test_data_exists(log_file: str) -> None:
    """Create dummy log file if not exists for testing."""
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")
        print(f"Created test log file: {log_file}")


def main() -> None:
    """Main entry point."""
    config = Config()

    # Ensure test data exists
    ensure_test_data_exists(config.log_file)

    # Run ETL pipeline
    pipeline = ETLPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
