"""Process server logs and generate an HTML report."""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<message>.*)$"
)
USER_ACTION_RE = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_CALL_RE = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: str
    db_user: str
    db_pass: str
    report_path: Path = Path("report.html")


@dataclass(frozen=True)
class LogRecord:
    """Base log record parsed from a single log line."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class UserEvent:
    """User session event extracted from the logs."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True)
class ApiCall:
    """API latency event extracted from the logs."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class ReportData:
    """Aggregated data needed for persistence and report rendering."""

    error_summary: Dict[str, int]
    api_latency: Dict[str, float]
    active_session_count: int


def load_config() -> Config:
    """Load configuration from environment variables."""

    return Config(
        db_path=Path(os.environ.get("DB_PATH", "metrics.db")),
        log_file=Path(os.environ.get("LOG_FILE", "server.log")),
        db_host=os.environ.get("DB_HOST", "localhost"),
        db_port=os.environ.get("DB_PORT", "5432"),
        db_user=os.environ.get("DB_USER", "admin"),
        db_pass=os.environ.get("DB_PASS", "password123"),
        report_path=Path(os.environ.get("REPORT_PATH", "report.html")),
    )


def extract_log_records(log_file: Path) -> List[LogRecord]:
    """Read and parse log lines from the configured log file."""

    if not log_file.exists():
        return []

    records: List[LogRecord] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            record = parse_log_line(raw_line)
            if record is not None:
                records.append(record)
    return records


def parse_log_line(line: str) -> Optional[LogRecord]:
    """Parse a single log line into a structured record."""

    match = LOG_LINE_RE.match(line.strip())
    if match is None:
        return None

    return LogRecord(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        message=match.group("message"),
    )


def transform_records(records: Iterable[LogRecord]) -> ReportData:
    """Transform raw log records into report-ready aggregates."""

    error_summary: Dict[str, int] = {}
    api_durations: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for record in records:
        if record.level == "ERROR":
            error_summary[record.message] = error_summary.get(record.message, 0) + 1
            continue

        if record.level == "INFO":
            user_event = parse_user_event(record)
            if user_event is not None:
                update_sessions(active_sessions, user_event)
                continue

            api_call = parse_api_call(record)
            if api_call is not None:
                api_durations.setdefault(api_call.endpoint, []).append(api_call.duration_ms)
                continue

    api_latency = {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in api_durations.items()
    }

    return ReportData(
        error_summary=error_summary,
        api_latency=api_latency,
        active_session_count=len(active_sessions),
    )


def parse_user_event(record: LogRecord) -> Optional[UserEvent]:
    """Parse a user event from an INFO log record."""

    match = USER_ACTION_RE.match(record.message)
    if match is None:
        return None

    return UserEvent(
        timestamp=record.timestamp,
        user_id=match.group("user_id"),
        action=match.group("action"),
    )


def update_sessions(active_sessions: Dict[str, str], event: UserEvent) -> None:
    """Update active session state based on a user event."""

    if "logged in" in event.action:
        active_sessions[event.user_id] = event.timestamp
    elif "logged out" in event.action:
        active_sessions.pop(event.user_id, None)


def parse_api_call(record: LogRecord) -> Optional[ApiCall]:
    """Parse an API latency event from an INFO log record."""

    match = API_CALL_RE.match(record.message)
    if match is None:
        return None

    duration_ms = int(match.group("duration_ms") or "0")
    return ApiCall(
        timestamp=record.timestamp,
        endpoint=match.group("endpoint"),
        duration_ms=duration_ms,
    )


def load_report_data(config: Config, report_data: ReportData) -> None:
    """Persist aggregated metrics to SQLite using parameterized queries."""

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    with sqlite3.connect(config.db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        now = dt.datetime.now().isoformat(sep=" ")
        for message, count in report_data.error_summary.items():
            cursor.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (now, message, count),
            )

        for endpoint, avg_ms in report_data.api_latency.items():
            cursor.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (now, endpoint, avg_ms),
            )


def render_report(report_data: ReportData) -> str:
    """Render the HTML report content."""

    output = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    output += "<h1>Error Summary</h1>\n<ul>\n"
    for error_message, count in report_data.error_summary.items():
        output += f"<li><b>{error_message}</b>: {count} occurrences</li>\n"
    output += "</ul>\n"

    output += "<h2>API Latency</h2>\n<table border='1'>\n"
    output += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, avg_ms in report_data.api_latency.items():
        output += f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>\n"
    output += "</table>\n"

    output += "<h2>Active Sessions</h2>\n"
    output += (
        f"<p>{report_data.active_session_count} user(s) currently active</p>"
    )
    output += "\n</body>\n</html>"
    return output


def write_report(report_path: Path, content: str) -> None:
    """Write the rendered HTML report to disk."""

    report_path.write_text(content, encoding="utf-8")


def ensure_sample_log(log_file: Path) -> None:
    """Create a sample log file when none exists."""

    if log_file.exists():
        return

    sample_log = (
        "2024-01-01 12:00:00 INFO User 42 logged in\n"
        "2024-01-01 12:05:00 ERROR Database timeout\n"
        "2024-01-01 12:05:05 ERROR Database timeout\n"
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
        "2024-01-01 12:10:00 INFO User 42 logged out\n"
    )
    log_file.write_text(sample_log, encoding="utf-8")


def run_pipeline() -> None:
    """Execute the extract-transform-load pipeline and generate the report."""

    config = load_config()
    ensure_sample_log(config.log_file)
    records = extract_log_records(config.log_file)
    report_data = transform_records(records)
    load_report_data(config, report_data)
    write_report(config.report_path, render_report(report_data))
    print(f"Job finished at {dt.datetime.now()}")


if __name__ == "__main__":
    run_pipeline()
