import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>INFO|WARN|ERROR) (?P<message>.*)$"
)
USER_ACTION_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")
REPORT_PATH = Path("report.html")
DEFAULT_LOG_CONTENT = """2024-01-01 12:00:00 INFO User 42 logged in
2024-01-01 12:05:00 ERROR Database timeout
2024-01-01 12:05:05 ERROR Database timeout
2024-01-01 12:08:00 INFO API /users/profile took 250ms
2024-01-01 12:09:00 WARN Memory usage at 87%
2024-01-01 12:10:00 INFO User 42 logged out
"""


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_password: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """Parsed error log entry."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class ApiCall:
    """Parsed API latency log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ParsedLogData:
    """Structured log data extracted from the source log file."""

    error_events: list[ErrorEvent]
    api_calls: list[ApiCall]
    active_sessions: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReportData:
    """Aggregated data used by the database load and HTML report."""

    error_summary: dict[str, int]
    api_latency: dict[str, float]
    active_session_count: int


def main() -> None:
    """Run the pipeline from extract through report generation."""
    config = load_config()
    ensure_log_file_exists(config.log_file)
    parsed_logs = extract_logs(config.log_file)
    report_data = transform_logs(parsed_logs)
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")
    load_metrics(config.db_path, report_data)
    write_report(REPORT_PATH, report_data)
    print(f"Job finished at {dt.datetime.now()}")


def load_config() -> Config:
    """Read pipeline configuration from environment variables."""
    return Config(
        db_path=Path(os.environ.get("PIPELINE_DB_PATH", "metrics.db")),
        log_file=Path(os.environ.get("PIPELINE_LOG_FILE", "server.log")),
        db_host=os.environ.get("PIPELINE_DB_HOST", "localhost"),
        db_port=int(os.environ.get("PIPELINE_DB_PORT", "5432")),
        db_user=os.environ.get("PIPELINE_DB_USER", "admin"),
        db_password=os.environ.get("PIPELINE_DB_PASSWORD", "password123"),
    )


def ensure_log_file_exists(log_file: Path) -> None:
    """Create a sample log file when the configured log file is missing."""
    if log_file.exists():
        return

    log_file.write_text(DEFAULT_LOG_CONTENT)


def extract_logs(log_file: Path) -> ParsedLogData:
    """Extract structured events and active session state from the log file."""
    error_events: list[ErrorEvent] = []
    api_calls: list[ApiCall] = []
    active_sessions: dict[str, str] = {}

    if not log_file.exists():
        return ParsedLogData(error_events, api_calls, active_sessions)

    with log_file.open("r") as handle:
        for line in handle:
            parsed_line = parse_log_line(line.strip())
            if parsed_line is None:
                continue

            timestamp, level, message = parsed_line
            if level == "ERROR":
                error_events.append(ErrorEvent(timestamp=timestamp, message=message))
                continue

            if level == "WARN":
                continue

            user_match = USER_ACTION_PATTERN.match(message)
            if user_match is not None:
                update_sessions(active_sessions, user_match.group("user_id"), user_match.group("action"), timestamp)
                continue

            api_match = API_PATTERN.match(message)
            if api_match is not None:
                duration_ms = int(api_match.group("duration_ms") or "0")
                api_calls.append(
                    ApiCall(
                        timestamp=timestamp,
                        endpoint=api_match.group("endpoint"),
                        duration_ms=duration_ms,
                    )
                )

    return ParsedLogData(error_events, api_calls, active_sessions)


def parse_log_line(line: str) -> tuple[str, str, str] | None:
    """Parse a single raw log line into timestamp, level, and message parts."""
    match = LOG_PATTERN.match(line)
    if match is None:
        return None

    return match.group("timestamp"), match.group("level"), match.group("message")


def update_sessions(active_sessions: dict[str, str], user_id: str, action: str, timestamp: str) -> None:
    """Apply a user login/logout action to the active session map."""
    if "logged in" in action:
        active_sessions[user_id] = timestamp
        return

    if "logged out" in action:
        active_sessions.pop(user_id, None)


def transform_logs(parsed_logs: ParsedLogData) -> ReportData:
    """Transform extracted log events into aggregated reporting metrics."""
    error_summary = summarize_errors(parsed_logs.error_events)
    api_latency = summarize_api_latency(parsed_logs.api_calls)
    return ReportData(
        error_summary=error_summary,
        api_latency=api_latency,
        active_session_count=len(parsed_logs.active_sessions),
    )


def summarize_errors(error_events: list[ErrorEvent]) -> dict[str, int]:
    """Count occurrences of each error message."""
    summary: dict[str, int] = {}
    for error_event in error_events:
        summary[error_event.message] = summary.get(error_event.message, 0) + 1
    return summary


def summarize_api_latency(api_calls: list[ApiCall]) -> dict[str, float]:
    """Compute average latency per API endpoint."""
    endpoint_durations: dict[str, list[int]] = {}
    for api_call in api_calls:
        endpoint_durations.setdefault(api_call.endpoint, []).append(api_call.duration_ms)

    return {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in endpoint_durations.items()
    }


def load_metrics(db_path: Path, report_data: ReportData) -> None:
    """Load aggregated metrics into the SQLite database using parameterized SQL."""
    recorded_at = str(dt.datetime.now())
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        for message, count in report_data.error_summary.items():
            cursor.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (recorded_at, message, count),
            )
        for endpoint, average_ms in report_data.api_latency.items():
            cursor.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (recorded_at, endpoint, average_ms),
            )
        connection.commit()


def write_report(report_path: Path, report_data: ReportData) -> None:
    """Write the HTML report with the same sections and information as before."""
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
    report_path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
