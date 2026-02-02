"""
Refactored ETL script following proper ETL pattern.
Maintains backward compatibility while improving maintainability.
"""

import os
import re
from typing import Any, Dict, List, Optional

# Configuration constants (extracted from hardcoded values)
DB_HOST = "localhost"
DB_USER = "admin"
LOG_FILE = "server.log"


class LogExtractor:
    """Extracts and parses log data using regex patterns."""

    # Regex patterns for robust parsing
    LOG_PATTERN = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) "
        r"(?P<level>\w+) (?P<message>.+)$"
    )
    USER_PATTERN = re.compile(r"User\s+(?P<user_id>\S+)")

    def __init__(self, log_file: str = LOG_FILE):
        self.log_file = log_file

    def extract(self) -> List[Dict[str, Any]]:
        """
        Extract log entries from file.

        Returns:
            List of parsed log entries as dictionaries
        """
        data: List[Dict[str, Any]] = []

        if not os.path.exists(self.log_file):
            return data

        try:
            with open(self.log_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    entry = self._parse_line(line.strip(), line_num)
                    if entry:
                        data.append(entry)
        except IOError as e:
            print(f"Error reading log file: {e}")

        return data

    def _parse_line(self, line: str, line_num: int) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line using regex.

        Args:
            line: Log line to parse
            line_num: Line number for error reporting

        Returns:
            Parsed log entry or None if line doesn't match
        """
        match = self.LOG_PATTERN.match(line)
        if not match:
            # Silently skip lines that don't match expected format
            return None

        date_str = f"{match.group('date')} {match.group('time')}"
        level = match.group("level")
        message = match.group("message")

        entry: Dict[str, Any] = {"date": date_str, "type": level, "msg": message}

        # Extract user ID from INFO messages containing "User"
        if level == "INFO" and "User" in message:
            user_match = self.USER_PATTERN.search(message)
            if user_match:
                entry["type"] = "USER_ACTION"
                entry["user"] = user_match.group("user_id")

        return entry


class DataTransformer:
    """Transforms extracted data into report format."""

    @staticmethod
    def transform_to_report(data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Transform log data into error count report.

        Args:
            data: List of parsed log entries

        Returns:
            Dictionary mapping error messages to their counts
        """
        report: Dict[str, int] = {}

        for item in data:
            if item.get("type") == "ERROR":
                msg = item.get("msg", "")
                if msg:
                    report[msg] = report.get(msg, 0) + 1

        return report


class ReportLoader:
    """Loads data by generating HTML reports."""

    @staticmethod
    def generate_html_report(
        report: Dict[str, int], output_file: str = "report.html"
    ) -> None:
        """
        Generate HTML report from error data.

        Args:
            report: Dictionary of error messages and counts
            output_file: Path to output HTML file
        """
        html_lines = ["<html>", "<body>", "<h1>Report</h1>", "<ul>"]

        # Sort errors by count (descending) for better readability
        for error_msg, count in sorted(
            report.items(), key=lambda x: x[1], reverse=True
        ):
            html_lines.append(f"<li>{error_msg}: {count}</li>")

        html_lines.extend(["</ul>", "</body>", "</html>"])

        try:
            with open(output_file, "w") as f:
                f.write("\n".join(html_lines))
        except IOError as e:
            print(f"Error writing report: {e}")


class DatabaseSimulator:
    """Simulates database operations for backward compatibility."""

    def __init__(self, host: str = DB_HOST, user: str = DB_USER):
        self.host = host
        self.user = user

    def connect(self) -> None:
        """Simulate database connection."""
        print(f"Connecting to {self.host} as {self.user}...")


class ETLPipeline:
    """Orchestrates the complete ETL process."""

    def __init__(self):
        self.extractor = LogExtractor()
        self.transformer = DataTransformer()
        self.loader = ReportLoader()
        self.db_simulator = DatabaseSimulator()

    def run(self) -> None:
        """Execute the complete ETL pipeline."""
        # Extract phase
        data = self.extractor.extract()

        # Simulate database operations (for backward compatibility)
        self.db_simulator.connect()

        # Transform phase
        report = self.transformer.transform_to_report(data)

        # Load phase
        self.loader.generate_html_report(report)

        print("Done.")


def create_sample_logs() -> None:
    """Create sample log file if it doesn't exist (for backward compatibility)."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")


def do_everything() -> None:
    """Main function for backward compatibility."""
    pipeline = ETLPipeline()
    pipeline.run()


if __name__ == "__main__":
    # Create dummy log file if not exists for testing
    create_sample_logs()

    # Run the ETL pipeline
    do_everything()
