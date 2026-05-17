from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) (?P<message>.*)$"
)
USER_EVENT_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_EVENT_PATTERN = re.compile(
    r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$"
)
DEFAULT_SAMPLE_LOG = (
    "2024-01-01 12:00:00 INFO User 42 logged in\n"
    "2024-01-01 12:05:00 ERROR Database timeout\n"
    "2024-01-01 12:05:05 ERROR Database timeout\n"
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
    "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
    "2024-01-01 12:10:00 INFO User 42 logged out\n"
)


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str
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
    """Structured data extracted from the log file."""

    errors: list[ErrorEvent]
    warnings: list[WarningEvent]
    user_events: list[UserEvent]
    api_calls: list[ApiCall]
    active_sessions: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReportData:
    """Aggregated data needed for persistence and HTML rendering."""

    error_summary: dict[str, int]
    api_latency: dict[str, float]
    active_session_count: int


def main() -> None:
    """Run the log processing pipeline end to end."""
    config = load_config()
    ensure_sample_log_exists(config.log_file)
    extracted = extract_data(config.log_file)
    report_data = transform_data(extracted)
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")
    load_data(config.db_path, report_data)
    report_html = render_report(report_data)
    write_report(config.report_path, report_html)
    print(f"Job finished at {dt.datetime.now()}")


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        db_path=Path(os.getenv("DB_PATH", "metrics.db")),
        log_file=Path(os.getenv("LOG_FILE", "server.log")),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_user=os.getenv("DB_USER", "admin"),
        db_pass=os.getenv("DB_PASS", "password123"),
        report_path=Path(os.getenv("REPORT_PATH", "report.html")),
    )


def ensure_sample_log_exists(log_file: Path) -> None:
    """Create the sample log file when no log file exists yet."""
    if log_file.exists():
        return
    log_file.write_text(DEFAULT_SAMPLE_LOG, encoding="utf-8")


def extract_data(log_file: Path) -> ExtractedData:
    """Extract structured events from the log file."""
    errors: list[ErrorEvent] = []
    warnings: list[WarningEvent] = []
    user_events: list[UserEvent] = []
    api_calls: list[ApiCall] = []
    active_sessions: dict[str, str] = {}

    if not log_file.exists():
        return ExtractedData(errors, warnings, user_events, api_calls, active_sessions)

    with log_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            parsed = parse_log_line(raw_line)
            if parsed is None:
                continue
            consume_event(parsed, errors, warnings, user_events, api_calls, active_sessions)

    return ExtractedData(errors, warnings, user_events, api_calls, active_sessions)


def parse_log_line(line: str) -> ErrorEvent | WarningEvent | UserEvent | ApiCall | None:
    """Parse a single log line into a typed event."""
    match = LOG_LINE_PATTERN.match(line.strip())
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
    """Parse INFO messages into user or API events."""
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

    duration = api_match.group("duration_ms") or "0"
    return ApiCall(
        timestamp=timestamp,
        endpoint=api_match.group("endpoint"),
        duration_ms=int(duration),
    )


def consume_event(
    event: ErrorEvent | WarningEvent | UserEvent | ApiCall,
    errors: list[ErrorEvent],
    warnings: list[WarningEvent],
    user_events: list[UserEvent],
    api_calls: list[ApiCall],
    active_sessions: dict[str, str],
) -> None:
    """Store a parsed event in the appropriate collection."""
    if isinstance(event, ErrorEvent):
        errors.append(event)
        return
    if isinstance(event, WarningEvent):
        warnings.append(event)
        return
    if isinstance(event, UserEvent):
        user_events.append(event)
        update_active_sessions(active_sessions, event)
        return
    api_calls.append(event)


def update_active_sessions(active_sessions: dict[str, str], event: UserEvent) -> None:
    """Update the active session map from a user event."""
    if "logged in" in event.action:
        active_sessions[event.user_id] = event.timestamp
        return
    if "logged out" in event.action:
        active_sessions.pop(event.user_id, None)


def transform_data(extracted: ExtractedData) -> ReportData:
    """Aggregate extracted events into reportable metrics."""
    error_summary = summarize_errors(extracted.errors)
    api_latency = summarize_api_latency(extracted.api_calls)
    return ReportData(
        error_summary=error_summary,
        api_latency=api_latency,
        active_session_count=len(extracted.active_sessions),
    )


def summarize_errors(errors: Iterable[ErrorEvent]) -> dict[str, int]:
    """Count occurrences of each error message."""
    summary: dict[str, int] = {}
    for event in errors:
        summary[event.message] = summary.get(event.message, 0) + 1
    return summary


def summarize_api_latency(api_calls: Iterable[ApiCall]) -> dict[str, float]:
    """Compute average latency per endpoint."""
    grouped_calls: dict[str, list[int]] = {}
    for call in api_calls:
        grouped_calls.setdefault(call.endpoint, []).append(call.duration_ms)

    averages: dict[str, float] = {}
    for endpoint, durations in grouped_calls.items():
        averages[endpoint] = sum(durations) / len(durations)
    return averages


def load_data(db_path: Path, report_data: ReportData) -> None:
    """Persist aggregated metrics to SQLite using parameterized queries."""
    now = str(dt.datetime.now())
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )
        cursor.executemany(
            "INSERT INTO errors VALUES (?, ?, ?)",
            [(now, message, count) for message, count in report_data.error_summary.items()],
        )
        cursor.executemany(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            [(now, endpoint, avg_ms) for endpoint, avg_ms in report_data.api_latency.items()],
        )
        connection.commit()


def render_report(report_data: ReportData) -> str:
    """Render the HTML report with the same information as before."""
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for message, count in report_data.error_summary.items():
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")

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


def write_report(report_path: Path, report_html: str) -> None:
    """Write the HTML report to disk."""
    report_path.write_text(report_html, encoding="utf-8")


if __name__ == "__main__":
    main()
