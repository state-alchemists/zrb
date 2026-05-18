"""
Log processing pipeline.

Reads server logs, extracts metrics, stores to SQLite, and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class DatabaseConnection(Protocol):
    """Protocol for database connection abstraction."""

    def cursor(self) -> "sqlite3.Cursor": ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


@dataclass
class LogEntry:
    """Represents a parsed log entry."""

    timestamp: str
    level: str
    message: str


@dataclass
class UserEvent:
    """Represents a user session event."""

    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """Represents an API call with latency information."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class ProcessedData:
    """Container for all processed data extracted from logs."""

    errors: list[LogEntry] = field(default_factory=list)
    warnings: list[LogEntry] = field(default_factory=list)
    user_events: list[UserEvent] = field(default_factory=list)
    api_calls: list[ApiCall] = field(default_factory=list)
    active_sessions: dict[str, str] = field(default_factory=dict)


class Config:
    """Configuration loaded from environment variables."""

    DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
    LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
    DB_HOST: str = os.environ.get("DB_HOST", "localhost")
    DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
    DB_USER: str = os.environ.get("DB_USER", "admin")
    DB_PASS: str = os.environ.get("DB_PASS", "password123")


class LogParser:
    """Parses log lines using regex patterns."""

    # Pattern: YYYY-MM-DD HH:MM:SS LEVEL message...
    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
        r"\s+(\w+)"
        r"\s+(.*)$"
    )

    # Pattern for user events: User ID action
    USER_PATTERN = re.compile(r"User\s+(\S+)\s+(.+)", re.IGNORECASE)

    # Pattern for API calls: API /endpoint took Xms
    API_PATTERN = re.compile(
        r"API\s+(\S+)\s+took\s+(\d+)ms",
        re.IGNORECASE
    )

    @staticmethod
    def parse_line(line: str) -> tuple[str, str, str] | None:
        """Parse a log line into timestamp, level, and message.

        Args:
            line: Raw log line to parse.

        Returns:
            Tuple of (timestamp, level, message) or None if parsing fails.
        """
        match = LogParser.LOG_PATTERN.match(line.strip())
        if not match:
            return None
        return match.group(1), match.group(2), match.group(3)

    @staticmethod
    def parse_user_event(message: str) -> tuple[str, str] | None:
        """Extract user ID and action from a user event message.

        Args:
            message: The log message containing user event info.

        Returns:
            Tuple of (user_id, action) or None if parsing fails.
        """
        match = LogParser.USER_PATTERN.search(message)
        if not match:
            return None
        return match.group(1), match.group(2)

    @staticmethod
    def parse_api_call(message: str) -> tuple[str, int] | None:
        """Extract endpoint and duration from an API call message.

        Args:
            message: The log message containing API call info.

        Returns:
            Tuple of (endpoint, duration_ms) or None if parsing fails.
        """
        match = LogParser.API_PATTERN.search(message)
        if not match:
            return None
        return match.group(1), int(match.group(2))


class LogExtractor:
    """Extracts structured data from log files."""

    def __init__(self, log_file_path: str) -> None:
        """Initialize extractor with log file path.

        Args:
            log_file_path: Path to the log file to read.
        """
        self.log_file_path = log_file_path

    def extract(self) -> ProcessedData:
        """Extract and categorize all entries from the log file.

        Returns:
            ProcessedData container with all extracted information.
        """
        data = ProcessedData()

        if not os.path.exists(self.log_file_path):
            return data

        with open(self.log_file_path, "r", encoding="utf-8") as file:
            for line in file:
                self._process_line(line.strip(), data)

        return data

    def _process_line(self, line: str, data: ProcessedData) -> None:
        """Process a single log line and update the data container.

        Args:
            line: Raw log line to process.
            data: Data container to update with extracted information.
        """
        parsed = LogParser.parse_line(line)
        if not parsed:
            return

        timestamp, level, message = parsed

        if level == "ERROR":
            data.errors.append(LogEntry(timestamp, level, message))

        elif level == "WARN":
            data.warnings.append(LogEntry(timestamp, level, message))

        elif level == "INFO":
            if "User" in line:
                user_data = LogParser.parse_user_event(message)
                if user_data:
                    user_id, action = user_data
                    data.user_events.append(
                        UserEvent(timestamp, user_id, action)
                    )
                    self._update_sessions(data.active_sessions, user_id, action)

            elif "API" in line:
                api_data = LogParser.parse_api_call(message)
                if api_data:
                    endpoint, duration = api_data
                    data.api_calls.append(
                        ApiCall(timestamp, endpoint, duration)
                    )

    def _update_sessions(
        self, sessions: dict[str, str], user_id: str, action: str
    ) -> None:
        """Update the active sessions dictionary based on user action.

        Args:
            sessions: Dictionary mapping user IDs to login timestamps.
            user_id: The ID of the user performing the action.
            action: The action performed by the user.
        """
        action_lower = action.lower()
        if "logged in" in action_lower:
            sessions[user_id] = datetime.datetime.now().isoformat()
        elif "logged out" in action_lower and user_id in sessions:
            del sessions[user_id]


class DataTransformer:
    """Transforms extracted data into aggregations for reporting."""

    @staticmethod
    def aggregate_errors(errors: list[LogEntry]) -> dict[str, int]:
        """Count occurrences of each error message.

        Args:
            errors: List of error log entries.

        Returns:
            Dictionary mapping error messages to occurrence counts.
        """
        counts: dict[str, int] = {}
        for entry in errors:
            counts[entry.message] = counts.get(entry.message, 0) + 1
        return counts

    @staticmethod
    def aggregate_api_latency(api_calls: list[ApiCall]) -> dict[str, float]:
        """Calculate average latency for each API endpoint.

        Args:
            api_calls: List of API call entries.

        Returns:
            Dictionary mapping endpoints to average response time in ms.
        """
        endpoint_times: dict[str, list[int]] = {}
        for call in api_calls:
            endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

        averages: dict[str, float] = {}
        for endpoint, times in endpoint_times.items():
            averages[endpoint] = sum(times) / len(times)
        return averages


class DatabaseLoader:
    """Loads processed data into SQLite database using parameterized queries."""

    def __init__(self, db_path: str) -> None:
        """Initialize loader with database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def load(
        self,
        error_counts: dict[str, int],
        api_averages: dict[str, float],
    ) -> None:
        """Load aggregated data into the database.

        Args:
            error_counts: Dictionary of error messages and their counts.
            api_averages: Dictionary of endpoints and their average latencies.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            self._create_tables(cursor)
            self._insert_errors(cursor, error_counts)
            self._insert_api_metrics(cursor, api_averages)
            conn.commit()
        finally:
            conn.close()

    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create database tables if they don't exist.

        Args:
            cursor: Database cursor for executing queries.
        """
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors "
            "(dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics "
            "(dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

    def _insert_errors(
        self, cursor: sqlite3.Cursor, error_counts: dict[str, int]
    ) -> None:
        """Insert error counts using parameterized queries.

        Args:
            cursor: Database cursor for executing queries.
            error_counts: Dictionary of error messages and their counts.
        """
        now = datetime.datetime.now().isoformat()
        cursor.executemany(
            "INSERT INTO errors VALUES (?, ?, ?)",
            [(now, msg, count) for msg, count in error_counts.items()]
        )

    def _insert_api_metrics(
        self, cursor: sqlite3.Cursor, api_averages: dict[str, float]
    ) -> None:
        """Insert API metrics using parameterized queries.

        Args:
            cursor: Database cursor for executing queries.
            api_averages: Dictionary of endpoints and their average latencies.
        """
        now = datetime.datetime.now().isoformat()
        cursor.executemany(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            [(now, ep, avg) for ep, avg in api_averages.items()]
        )


class ReportGenerator:
    """Generates HTML reports from processed data."""

    def __init__(self, output_path: str) -> None:
        """Initialize generator with output path.

        Args:
            output_path: Path where the HTML report will be written.
        """
        self.output_path = output_path

    def generate(
        self,
        error_counts: dict[str, int],
        api_averages: dict[str, float],
        active_session_count: int,
    ) -> None:
        """Generate and write the HTML report.

        Args:
            error_counts: Dictionary of error messages and occurrence counts.
            api_averages: Dictionary of endpoints and average latencies.
            active_session_count: Number of currently active user sessions.
        """
        html = self._render_html(error_counts, api_averages, active_session_count)
        with open(self.output_path, "w", encoding="utf-8") as file:
            file.write(html)

    def _render_html(
        self,
        error_counts: dict[str, int],
        api_averages: dict[str, float],
        active_session_count: int,
    ) -> str:
        """Render the HTML report content.

        Args:
            error_counts: Dictionary of error messages and occurrence counts.
            api_averages: Dictionary of endpoints and average latencies.
            active_session_count: Number of currently active user sessions.

        Returns:
            Complete HTML document as a string.
        """
        lines = [
            "<html>",
            "<head><title>System Report</title></head>",
            "<body>",
            "<h1>Error Summary</h1>",
            "<ul>",
        ]

        for err_msg, count in error_counts.items():
            escaped_msg = err_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"<li><b>{escaped_msg}</b>: {count} occurrences</li>")

        lines.extend([
            "</ul>",
            "<h2>API Latency</h2>",
            "<table border='1'>",
            "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
        ])

        for ep, avg in api_averages.items():
            escaped_ep = ep.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"<tr><td>{escaped_ep}</td><td>{round(avg, 1)}</td></tr>")

        lines.extend([
            "</table>",
            "<h2>Active Sessions</h2>",
            f"<p>{active_session_count} user(s) currently active</p>",
            "</body>",
            "</html>",
        ])

        return "\n".join(lines)


def create_sample_log(log_file_path: str) -> None:
    """Create a sample log file if none exists.

    Args:
        log_file_path: Path where the sample log file should be created.
    """
    if os.path.exists(log_file_path):
        return

    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]

    Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_file_path, "w", encoding="utf-8") as file:
        file.write("\n".join(sample_lines) + "\n")


def run_pipeline(
    log_file_path: str = Config.LOG_FILE,
    db_path: str = Config.DB_PATH,
    report_path: str = "report.html",
) -> None:
    """Execute the complete ETL pipeline.

    Args:
        log_file_path: Path to the log file to process.
        db_path: Path to the SQLite database.
        report_path: Path where the HTML report will be written.
    """
    # Extract
    extractor = LogExtractor(log_file_path)
    data = extractor.extract()

    # Transform
    transformer = DataTransformer()
    error_counts = transformer.aggregate_errors(data.errors)
    api_averages = transformer.aggregate_api_latency(data.api_calls)

    # Load
    print(f"Connecting to {Config.DB_HOST}:{Config.DB_PORT} as {Config.DB_USER}...")
    loader = DatabaseLoader(db_path)
    loader.load(error_counts, api_averages)

    # Generate Report
    generator = ReportGenerator(report_path)
    generator.generate(error_counts, api_averages, len(data.active_sessions))

    print(f"Job finished at {datetime.datetime.now()}")


def main() -> None:
    """Main entry point for the pipeline."""
    create_sample_log(Config.LOG_FILE)
    run_pipeline()


if __name__ == "__main__":
    main()
