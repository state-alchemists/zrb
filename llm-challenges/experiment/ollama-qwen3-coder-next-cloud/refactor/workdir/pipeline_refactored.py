"""Server log pipeline: ETL from logs to database and HTML report.

This script processes server logs, extracts error messages and API metrics,
loads them into a SQLite database, and generates an HTML report.

Environment Variables:
    LOG_FILE: Path to the server log file (default: "server.log")
    DB_PATH: Path to the SQLite database file (default: "metrics.db")
    REPORT_PATH: Path to the output HTML report (default: "report.html")
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


@dataclass(frozen=True)
class LogEntry:
    """Represents a parsed log line."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class ErrorEntry:
    """Represents an error message with its count."""

    timestamp: datetime.datetime
    message: str
    count: int


@dataclass(frozen=True)
class ApiMetric:
    """Represents API endpoint latency data."""

    timestamp: datetime.datetime
    endpoint: str
    avg_ms: float


class SessionTracker:
    """Tracks active user sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}

    def login(self, user_id: str, timestamp: str) -> None:
        """Record a user login."""
        self._sessions[user_id] = timestamp

    def logout(self, user_id: str) -> None:
        """Record a user logout."""
        self._sessions.pop(user_id, None)

    @property
    def active_count(self) -> int:
        """Return the number of currently active sessions."""
        return len(self._sessions)


class Config:
    """Configuration sourced from environment variables."""

    def __init__(self) -> None:
        self.log_file = Path(os.getenv("LOG_FILE", "server.log"))
        self.db_path = Path(os.getenv("DB_PATH", "metrics.db"))
        self.report_path = Path(os.getenv("REPORT_PATH", "report.html"))


# Regex patterns for log parsing
LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(INFO|ERROR|WARN)\s+(.*)$"
)
USER_LOGGED_IN = re.compile(r"User\s+(\d+)\s+logged\s+in")
USER_LOGGED_OUT = re.compile(r"User\s+(\d+)\s+logged\s+out")
API_CALL = re.compile(r"API\s+(\S+)\s+took\s+(\d+)ms")


class LogParser:
    """Parses server log files and extracts structured data."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path

    def parse(self) -> tuple[list[LogEntry], dict[str, str], list[dict[str, str | float]]]:
        """
        Parse the log file and extract errors, sessions, and API metrics.

        Returns:
            Tuple of (error list, session dict, API calls list).
        """
        entries: list[LogEntry] = []
        sessions: dict[str, str] = {}
        api_calls: list[dict[str, str | float]] = []

        if not self.log_path.exists():
            return entries, sessions, api_calls

        with self.log_path.open() as f:
            for line in f:
                entry = self._parse_line(line.strip())
                if entry:
                    entries.append(entry)
                    self._extract_session(entry, sessions)
                    self._extract_api_metric(entry, api_calls)

        return entries, sessions, api_calls

    def _parse_line(self, line: str) -> LogEntry | None:
        """Parse a single log line into a LogEntry."""
        match = LOG_PATTERN.match(line)
        if not match:
            return None

        timestamp, level, message = match.groups()
        return LogEntry(timestamp=timestamp, level=level, message=message)

    def _extract_session(
        self, entry: LogEntry, sessions: dict[str, str]
    ) -> None:
        """Update session state from a log entry."""
        if entry.level != "INFO":
            return

        # Check for login
        match = USER_LOGGED_IN.search(entry.message)
        if match:
            user_id = match.group(1)
            sessions[user_id] = entry.timestamp
            return

        # Check for logout
        match = USER_LOGGED_OUT.search(entry.message)
        if match:
            user_id = match.group(1)
            sessions.pop(user_id, None)

    def _extract_api_metric(
        self, entry: LogEntry, api_calls: list[dict[str, str | float]]
    ) -> None:
        """Extract API latency from a log entry."""
        if entry.level != "INFO":
            return

        match = API_CALL.search(entry.message)
        if match:
            endpoint = match.group(1)
            duration_ms = int(match.group(2))
            api_calls.append({"endpoint": endpoint, "ms": duration_ms})

    def _extract_error(self, entry: LogEntry) -> str | None:
        """Extract error message from a log entry."""
        if entry.level != "ERROR":
            return None
        return entry.message


class DatabaseWriter:
    """Writes ETL results to SQLite database using parameterized queries."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def __enter__(self) -> "DatabaseWriter":
        """Open database connection on context enter."""
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()
        return self

    def __exit__(self, *_: object) -> None:
        """Commit and close connection on context exit."""
        self.conn.commit()
        self.conn.close()

    def _create_tables(self) -> None:
        """Create required tables if they don't exist."""
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS errors (
                    dt TEXT,
                    message TEXT,
                    count INTEGER
                )
            """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_metrics (
                    dt TEXT,
                    endpoint TEXT,
                    avg_ms REAL
                )
            """
            )

    def insert_errors(self, errors: list[ErrorEntry]) -> None:
        """Insert error records using parameterized queries."""
        for err in errors:
            self.conn.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (err.timestamp, err.message, err.count),
            )

    def insert_api_metrics(self, metrics: list[ApiMetric]) -> None:
        """Insert API metric records using parameterized queries."""
        for metric in metrics:
            self.conn.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (metric.timestamp, metric.endpoint, metric.avg_ms),
            )


class ReportBuilder:
    """Builds HTML report from ETL results."""

    def __init__(self, errors: dict[str, int]) -> None:
        self.errors = errors

    def build(
        self,
        api_metrics: dict[str, list[float]],
        active_sessions: int,
    ) -> str:
        """
        Build the HTML report.

        Args:
            api_metrics: Dict mapping endpoints to their latency lists.
            active_sessions: Number of currently active user sessions.

        Returns:
            Complete HTML report as a string.
        """
        lines = [
            "<html>",
            "<head><title>System Report</title></head>",
            "<body>",
            "<h1>Error Summary</h1>",
            "<ul>",
        ]

        for msg, count in self.errors.items():
            lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
        lines.extend(["</ul>"])

        lines.extend(
            [
                "<h2>API Latency</h2>",
                "<table border='1'>",
                "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
            ]
        )

        for endpoint, times in api_metrics.items():
            avg = sum(times) / len(times)
            lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")
        lines.extend(
            [
                "</table>",
                "<h2>Active Sessions</h2>",
                f"<p>{active_sessions} user(s) currently active</p>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(lines)


def extract_errors(entries: list[LogEntry]) -> dict[str, int]:
    """Aggregate error messages and counts."""
    counts: dict[str, int] = {}
    for entry in entries:
        if entry.level == "ERROR":
            counts[entry.message] = counts.get(entry.message, 0) + 1
    return counts


def transform_api_metrics(api_calls: list[dict[str, str | float]]) -> dict[str, list[float]]:
    """Group API calls by endpoint."""
    metrics: dict[str, list[float]] = {}
    for call in api_calls:
        endpoint = str(call["endpoint"])
        duration = float(call["ms"])
        metrics.setdefault(endpoint, []).append(duration)
    return metrics


def load_to_db(
    db: DatabaseWriter, errors: dict[str, int], api_metrics: dict[str, list[float]]
) -> None:
    """Load error and API metric data into the database."""
    now = datetime.datetime.now().isoformat()

    error_records = [
        ErrorEntry(timestamp=now, message=msg, count=count)
        for msg, count in errors.items()
    ]
    db.insert_errors(error_records)

    metric_records = [
        ApiMetric(
            timestamp=now,
            endpoint=endpoint,
            avg_ms=sum(times) / len(times),
        )
        for endpoint, times in api_metrics.items()
    ]
    db.insert_api_metrics(metric_records)


def write_report(report: ReportBuilder, api_metrics: dict[str, list[float]], active_sessions: int, path: Path) -> None:
    """Write the HTML report to a file."""
    html = report.build(api_metrics, active_sessions)
    path.write_text(html)


def main() -> None:
    """Main entry point for the ETL pipeline."""
    config = Config()
    parser = LogParser(config.log_file)
    now = datetime.datetime.now()

    # Extract
    entries, sessions, api_calls = parser.parse()

    # Transform
    errors = extract_errors(entries)
    api_metrics = transform_api_metrics(api_calls)
    session_tracker = SessionTracker()
    for uid, timestamp in sessions.items():
        session_tracker.login(uid, timestamp)
        # Check for logout in entries to update session
        for entry in entries:
            if entry.level == "INFO":
                match = USER_LOGGED_OUT.search(entry.message)
                if match and match.group(1) == uid:
                    session_tracker.logout(uid)

    active_sessions = session_tracker.active_count

    # Load
    with DatabaseWriter(config.db_path) as db:
        load_to_db(db, errors, api_metrics)

    # Report
    report = ReportBuilder(errors)
    write_report(report, api_metrics, active_sessions, config.report_path)

    print(f"Job finished at {now}")


if __name__ == "__main__":
    # Create sample log file if it doesn't exist
    if not Path("server.log").exists():
        Path("server.log").write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )
    main()
