import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>INFO|WARN|ERROR) (?P<message>.*)$"
)
USER_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file_path: Path
    report_path: Path
    db_host: str
    db_port: str
    db_user: str
    db_password: str


@dataclass(frozen=True)
class LogEntry:
    """A parsed server log entry."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class UserEvent:
    """A parsed user session event."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True)
class ApiCall:
    """A parsed API latency event."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class ReportData:
    """Aggregated values required to render the report and persist metrics."""

    error_summary: dict[str, int]
    api_latency: dict[str, float]
    active_session_count: int


def get_env(name: str, default: str | None = None) -> str:
    """Return an environment variable value, optionally falling back to a default."""

    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    """Load application configuration from environment variables."""

    return Config(
        db_path=Path(get_env("PIPELINE_DB_PATH", "metrics.db")),
        log_file_path=Path(get_env("PIPELINE_LOG_FILE", "server.log")),
        report_path=Path(get_env("PIPELINE_REPORT_PATH", "report.html")),
        db_host=get_env("PIPELINE_DB_HOST", "localhost"),
        db_port=get_env("PIPELINE_DB_PORT", "5432"),
        db_user=get_env("PIPELINE_DB_USER", "admin"),
        db_password=get_env("PIPELINE_DB_PASS", "password123"),
    )


def ensure_sample_log_exists(log_file_path: Path) -> None:
    """Create the sample log file used by the original script when missing."""

    if log_file_path.exists():
        return

    log_file_path.write_text(
        """2024-01-01 12:00:00 INFO User 42 logged in\n2024-01-01 12:05:00 ERROR Database timeout\n2024-01-01 12:05:05 ERROR Database timeout\n2024-01-01 12:08:00 INFO API /users/profile took 250ms\n2024-01-01 12:09:00 WARN Memory usage at 87%\n2024-01-01 12:10:00 INFO User 42 logged out\n""",
        encoding="utf-8",
    )


def parse_log_line(line: str) -> LogEntry | None:
    """Parse a raw log line into a structured log entry."""

    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    return LogEntry(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        message=match.group("message"),
    )


def extract_log_entries(log_file_path: Path) -> list[LogEntry]:
    """Extract structured log entries from the configured log file."""

    if not log_file_path.exists():
        return []

    entries: list[LogEntry] = []
    with log_file_path.open("r", encoding="utf-8") as log_file:
        for line in log_file:
            entry = parse_log_line(line)
            if entry is not None:
                entries.append(entry)
    return entries


def extract_user_event(entry: LogEntry) -> UserEvent | None:
    """Extract a user session event from an INFO log entry when present."""

    if entry.level != "INFO":
        return None

    match = USER_PATTERN.match(entry.message)
    if not match:
        return None

    return UserEvent(
        timestamp=entry.timestamp,
        user_id=match.group("user_id"),
        action=match.group("action"),
    )


def extract_api_call(entry: LogEntry) -> ApiCall | None:
    """Extract an API latency record from an INFO log entry when present."""

    if entry.level != "INFO":
        return None

    match = API_PATTERN.match(entry.message)
    if not match:
        return None

    duration_ms = int(match.group("duration_ms") or "0")
    return ApiCall(
        timestamp=entry.timestamp,
        endpoint=match.group("endpoint"),
        duration_ms=duration_ms,
    )


def summarize_errors(entries: Iterable[LogEntry]) -> dict[str, int]:
    """Count error messages by exact message text."""

    error_summary: dict[str, int] = {}
    for entry in entries:
        if entry.level == "ERROR":
            error_summary[entry.message] = error_summary.get(entry.message, 0) + 1
    return error_summary


def summarize_api_latency(api_calls: Iterable[ApiCall]) -> dict[str, float]:
    """Compute average latency per API endpoint."""

    grouped_calls: dict[str, list[int]] = {}
    for call in api_calls:
        grouped_calls.setdefault(call.endpoint, []).append(call.duration_ms)

    return {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in grouped_calls.items()
    }


def count_active_sessions(user_events: Iterable[UserEvent]) -> int:
    """Track logins and logouts to determine the active session count."""

    sessions: dict[str, str] = {}
    for event in user_events:
        if "logged in" in event.action:
            sessions[event.user_id] = event.timestamp
        elif "logged out" in event.action:
            sessions.pop(event.user_id, None)
    return len(sessions)


def transform(entries: Sequence[LogEntry]) -> ReportData:
    """Transform extracted log entries into report-ready aggregates."""

    user_events = [event for entry in entries if (event := extract_user_event(entry)) is not None]
    api_calls = [call for entry in entries if (call := extract_api_call(entry)) is not None]

    return ReportData(
        error_summary=summarize_errors(entries),
        api_latency=summarize_api_latency(api_calls),
        active_session_count=count_active_sessions(user_events),
    )


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create required tables if they do not already exist."""

    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")


def load_metrics(db_path: Path, report_data: ReportData, captured_at: dt.datetime) -> None:
    """Persist aggregated metrics using parameterized SQL statements."""

    connection = sqlite3.connect(db_path)
    try:
        initialize_database(connection)
        cursor = connection.cursor()

        cursor.executemany(
            "INSERT INTO errors VALUES (?, ?, ?)",
            [
                (captured_at.isoformat(sep=" "), message, count)
                for message, count in report_data.error_summary.items()
            ],
        )
        cursor.executemany(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            [
                (captured_at.isoformat(sep=" "), endpoint, avg_ms)
                for endpoint, avg_ms in report_data.api_latency.items()
            ],
        )

        connection.commit()
    finally:
        connection.close()


def build_report_html(report_data: ReportData) -> str:
    """Render the HTML report with the same information as the original script."""

    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for error_message, count in report_data.error_summary.items():
        lines.append(f"<li><b>{error_message}</b>: {count} occurrences</li>")

    lines.extend(
        [
            "</ul>",
            "<h2>API Latency</h2>",
            "<table border='1'>",
            "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
        ]
    )

    for endpoint, avg_ms in report_data.api_latency.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>")

    lines.extend(
        [
            "</table>",
            "<h2>Active Sessions</h2>",
            f"<p>{report_data.active_session_count} user(s) currently active</p>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(lines)


def write_report(report_path: Path, report_data: ReportData) -> None:
    """Write the rendered HTML report to disk."""

    report_path.write_text(build_report_html(report_data), encoding="utf-8")


def run_pipeline() -> None:
    """Execute the Extract → Transform → Load pipeline and generate the report."""

    config = load_config()
    ensure_sample_log_exists(config.log_file_path)

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    entries = extract_log_entries(config.log_file_path)
    report_data = transform(entries)
    captured_at = dt.datetime.now()

    load_metrics(config.db_path, report_data, captured_at)
    write_report(config.report_path, report_data)

    print(f"Job finished at {captured_at}")


if __name__ == "__main__":
    run_pipeline()
