from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>ERROR|INFO|WARN) (?P<message>.*)$"
)
USER_EVENT_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_EVENT_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")
DEFAULT_REPORT_FILE = "report.html"
DEFAULT_SAMPLE_LOG = "\n".join(
    [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
) + "\n"


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    report_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True, slots=True)
class ParsedLogLine:
    """Normalized representation of a parsed log line."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    """Parsed error event from the log stream."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class UserEvent:
    """Parsed user session event from the log stream."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiCall:
    """Parsed API timing event from the log stream."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ExtractedData:
    """Raw events extracted from the log file."""

    errors: list[ErrorRecord]
    user_events: list[UserEvent]
    api_calls: list[ApiCall]


@dataclass(frozen=True, slots=True)
class ReportData:
    """Aggregated data needed for database writes and report rendering."""

    error_summary: dict[str, int]
    api_latency: dict[str, float]
    active_session_count: int


def load_config() -> Config:
    """Load required configuration from environment variables."""
    return Config(
        db_path=Path(require_env("DB_PATH")),
        log_file=Path(require_env("LOG_FILE")),
        report_file=Path(os.getenv("REPORT_FILE", DEFAULT_REPORT_FILE)),
        db_host=require_env("DB_HOST"),
        db_port=int(require_env("DB_PORT")),
        db_user=require_env("DB_USER"),
        db_pass=require_env("DB_PASS"),
    )


def require_env(name: str) -> str:
    """Return a non-empty environment variable or raise a clear error."""
    value = os.getenv(name)
    if value:
        return value
    raise ValueError(f"Missing required environment variable: {name}")


def run_pipeline(config: Config) -> None:
    """Run the full extract, transform, and load pipeline."""
    ensure_sample_log_exists(config.log_file)
    extracted = extract_logs(config.log_file)
    report_data = transform_data(extracted)
    print_connection_message(config)
    load_metrics(config.db_path, report_data)
    render_report(config.report_file, report_data)
    print(f"Job finished at {dt.datetime.now()}")


def ensure_sample_log_exists(log_file: Path) -> None:
    """Create the sample log file when the configured log file does not exist."""
    if log_file.exists():
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(DEFAULT_SAMPLE_LOG, encoding="utf-8")


def extract_logs(log_file: Path) -> ExtractedData:
    """Extract structured events from the configured log file."""
    errors: list[ErrorRecord] = []
    user_events: list[UserEvent] = []
    api_calls: list[ApiCall] = []

    with log_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            parsed = parse_log_line(raw_line)
            if parsed is None:
                continue
            if parsed.level == "ERROR":
                errors.append(ErrorRecord(parsed.timestamp, parsed.message))
                continue
            if parsed.level == "WARN":
                continue
            user_event = parse_user_event(parsed)
            if user_event is not None:
                user_events.append(user_event)
                continue
            api_event = parse_api_call(parsed)
            if api_event is not None:
                api_calls.append(api_event)

    return ExtractedData(errors=errors, user_events=user_events, api_calls=api_calls)


def parse_log_line(raw_line: str) -> ParsedLogLine | None:
    """Parse a raw log line into timestamp, level, and message fields."""
    match = LOG_LINE_PATTERN.match(raw_line.strip())
    if match is None:
        return None
    return ParsedLogLine(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        message=match.group("message"),
    )


def parse_user_event(parsed: ParsedLogLine) -> UserEvent | None:
    """Parse a user session event from an INFO log line."""
    match = USER_EVENT_PATTERN.match(parsed.message)
    if match is None:
        return None
    return UserEvent(
        timestamp=parsed.timestamp,
        user_id=match.group("user_id"),
        action=match.group("action"),
    )


def parse_api_call(parsed: ParsedLogLine) -> ApiCall | None:
    """Parse an API latency event from an INFO log line."""
    match = API_EVENT_PATTERN.match(parsed.message)
    if match is None:
        return None
    duration_text = match.group("duration_ms") or "0"
    return ApiCall(
        timestamp=parsed.timestamp,
        endpoint=match.group("endpoint"),
        duration_ms=int(duration_text),
    )


def transform_data(extracted: ExtractedData) -> ReportData:
    """Transform extracted events into report and persistence aggregates."""
    return ReportData(
        error_summary=summarize_errors(extracted.errors),
        api_latency=calculate_api_latency(extracted.api_calls),
        active_session_count=count_active_sessions(extracted.user_events),
    )


def summarize_errors(errors: list[ErrorRecord]) -> dict[str, int]:
    """Count occurrences of each error message."""
    summary: dict[str, int] = {}
    for error in errors:
        summary[error.message] = summary.get(error.message, 0) + 1
    return summary


def calculate_api_latency(api_calls: list[ApiCall]) -> dict[str, float]:
    """Calculate average latency by endpoint."""
    grouped: dict[str, list[int]] = {}
    for call in api_calls:
        grouped.setdefault(call.endpoint, []).append(call.duration_ms)
    return {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in grouped.items()
    }


def count_active_sessions(events: list[UserEvent]) -> int:
    """Count currently active user sessions from login/logout events."""
    active_sessions: dict[str, str] = {}
    for event in events:
        if "logged in" in event.action:
            active_sessions[event.user_id] = event.timestamp
            continue
        if "logged out" in event.action:
            active_sessions.pop(event.user_id, None)
    return len(active_sessions)


def print_connection_message(config: Config) -> None:
    """Print the database connection message without exposing the password."""
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")


def load_metrics(db_path: Path, report_data: ReportData) -> None:
    """Persist aggregated metrics using parameterized SQL statements."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = str(dt.datetime.now())

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
            [
                (generated_at, message, count)
                for message, count in report_data.error_summary.items()
            ],
        )
        cursor.executemany(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            [
                (generated_at, endpoint, average)
                for endpoint, average in report_data.api_latency.items()
            ],
        )


def render_report(report_file: Path, report_data: ReportData) -> None:
    """Render the HTML report with the same sections as the legacy script."""
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(build_report_html(report_data), encoding="utf-8")


def build_report_html(report_data: ReportData) -> str:
    """Build the HTML report body."""
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
    for endpoint, average in report_data.api_latency.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{round(average, 1)}</td></tr>")
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


if __name__ == "__main__":
    run_pipeline(load_config())
