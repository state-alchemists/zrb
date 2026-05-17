from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_REPORT_PATH = "report.html"
DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_USER = "admin"
DEFAULT_DB_PASSWORD = "password123"
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|WARN|ERROR) (?P<message>.*)$"
)
USER_EVENT_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_EVENT_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")
SAMPLE_LOG_LINES = (
    "2024-01-01 12:00:00 INFO User 42 logged in\n",
    "2024-01-01 12:05:00 ERROR Database timeout\n",
    "2024-01-01 12:05:05 ERROR Database timeout\n",
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
    "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
    "2024-01-01 12:10:00 INFO User 42 logged out\n",
)


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    report_path: Path


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """A parsed error log event."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class WarningEvent:
    """A parsed warning log event."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class UserEvent:
    """A parsed user session log event."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiCall:
    """A parsed API latency log event."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ExtractedData:
    """Raw data extracted from the source log file."""

    errors: list[ErrorEvent]
    warnings: list[WarningEvent]
    user_events: list[UserEvent]
    api_calls: list[ApiCall]
    active_sessions: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReportData:
    """Aggregated metrics used for persistence and report generation."""

    error_summary: dict[str, int]
    api_latency: dict[str, float]
    active_session_count: int


def main() -> None:
    """Run the ETL pipeline and generate the HTML report."""
    config = load_config()
    ensure_sample_log_exists(config.log_file)
    extracted_data = extract_log_data(config.log_file)
    report_data = transform_log_data(extracted_data)
    load_metrics(report_data, config.db_path)
    write_report(report_data, config.report_path)
    print_connection_message(config)
    print(f"Job finished at {dt.datetime.now()}")


def load_config() -> Config:
    """Load all runtime settings from environment variables."""
    return Config(
        db_path=Path(get_required_env("PIPELINE_DB_PATH")),
        log_file=Path(get_required_env("PIPELINE_LOG_FILE")),
        db_host=os.environ.get("PIPELINE_DB_HOST", DEFAULT_DB_HOST),
        db_port=int(os.environ.get("PIPELINE_DB_PORT", str(DEFAULT_DB_PORT))),
        db_user=os.environ.get("PIPELINE_DB_USER", DEFAULT_DB_USER),
        db_password=os.environ.get("PIPELINE_DB_PASSWORD", DEFAULT_DB_PASSWORD),
        report_path=Path(os.environ.get("PIPELINE_REPORT_FILE", DEFAULT_REPORT_PATH)),
    )


def get_required_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.environ.get(name)
    if value:
        return value
    raise ValueError(f"Environment variable {name} is required")


def ensure_sample_log_exists(log_file: Path) -> None:
    """Create the sample log file used by the original script when absent."""
    if log_file.exists():
        return
    with log_file.open("w", encoding="utf-8") as handle:
        handle.writelines(SAMPLE_LOG_LINES)


def extract_log_data(log_file: Path) -> ExtractedData:
    """Extract structured events and active session state from the log file."""
    errors: list[ErrorEvent] = []
    warnings: list[WarningEvent] = []
    user_events: list[UserEvent] = []
    api_calls: list[ApiCall] = []
    active_sessions: dict[str, str] = {}

    if not log_file.exists():
        return ExtractedData(errors, warnings, user_events, api_calls, active_sessions)

    with log_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            parsed = parse_log_line(raw_line.rstrip("\n"))
            if parsed is None:
                continue
            if isinstance(parsed, ErrorEvent):
                errors.append(parsed)
            elif isinstance(parsed, WarningEvent):
                warnings.append(parsed)
            elif isinstance(parsed, UserEvent):
                user_events.append(parsed)
                update_sessions(active_sessions, parsed)
            else:
                api_calls.append(parsed)

    return ExtractedData(errors, warnings, user_events, api_calls, active_sessions)


def parse_log_line(line: str) -> ErrorEvent | WarningEvent | UserEvent | ApiCall | None:
    """Parse one log line into a typed event using regex patterns."""
    match = LOG_PATTERN.match(line)
    if match is None:
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    message = match.group("message")

    if level == "ERROR":
        return ErrorEvent(timestamp=timestamp, message=message)
    if level == "WARN":
        return WarningEvent(timestamp=timestamp, message=message)
    return parse_info_event(timestamp, message)


def parse_info_event(timestamp: str, message: str) -> UserEvent | ApiCall | None:
    """Parse INFO log messages into user or API events."""
    user_match = USER_EVENT_PATTERN.match(message)
    if user_match is not None:
        return UserEvent(
            timestamp=timestamp,
            user_id=user_match.group("user_id"),
            action=user_match.group("action"),
        )

    api_match = API_EVENT_PATTERN.match(message)
    if api_match is None:
        return None

    duration_text = api_match.group("duration_ms") or "0"
    return ApiCall(
        timestamp=timestamp,
        endpoint=api_match.group("endpoint"),
        duration_ms=int(duration_text),
    )


def update_sessions(active_sessions: dict[str, str], event: UserEvent) -> None:
    """Update the active session map based on a user event."""
    if "logged in" in event.action:
        active_sessions[event.user_id] = event.timestamp
        return
    if "logged out" in event.action:
        active_sessions.pop(event.user_id, None)


def transform_log_data(extracted_data: ExtractedData) -> ReportData:
    """Aggregate extracted events into reportable and persistable metrics."""
    return ReportData(
        error_summary=summarize_errors(extracted_data.errors),
        api_latency=calculate_api_latency(extracted_data.api_calls),
        active_session_count=len(extracted_data.active_sessions),
    )


def summarize_errors(errors: Iterable[ErrorEvent]) -> dict[str, int]:
    """Count how many times each error message appears."""
    summary: dict[str, int] = {}
    for error in errors:
        summary[error.message] = summary.get(error.message, 0) + 1
    return summary


def calculate_api_latency(api_calls: Iterable[ApiCall]) -> dict[str, float]:
    """Compute average latency in milliseconds for each endpoint."""
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    averages: dict[str, float] = {}
    for endpoint, times in endpoint_times.items():
        averages[endpoint] = sum(times) / len(times)
    return averages


def load_metrics(report_data: ReportData, db_path: Path) -> None:
    """Persist aggregated metrics into SQLite using parameterized queries."""
    now = str(dt.datetime.now())
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )
        insert_error_rows(cursor, now, report_data.error_summary)
        insert_api_metric_rows(cursor, now, report_data.api_latency)
        connection.commit()


def insert_error_rows(
    cursor: sqlite3.Cursor, timestamp: str, error_summary: dict[str, int]
) -> None:
    """Insert aggregated error rows into SQLite."""
    for message, count in error_summary.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (timestamp, message, count),
        )


def insert_api_metric_rows(
    cursor: sqlite3.Cursor, timestamp: str, api_latency: dict[str, float]
) -> None:
    """Insert aggregated API latency rows into SQLite."""
    for endpoint, average_ms in api_latency.items():
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (timestamp, endpoint, average_ms),
        )


def write_report(report_data: ReportData, report_path: Path) -> None:
    """Write the HTML report with the same information as the original script."""
    report_path.write_text(render_report(report_data), encoding="utf-8")


def render_report(report_data: ReportData) -> str:
    """Render the HTML report body."""
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
    for endpoint, average_ms in report_data.api_latency.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{round(average_ms, 1)}</td></tr>")
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


def print_connection_message(config: Config) -> None:
    """Print the connection status message used by the original script."""
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")


if __name__ == "__main__":
    main()
