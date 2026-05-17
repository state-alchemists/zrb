import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REPORT_PATH = "report.html"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN)"
    r"(?: (?P<message>.*))?$"
)
USER_ACTION_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")
SAMPLE_LOG_LINES = [
    "2024-01-01 12:00:00 INFO User 42 logged in",
    "2024-01-01 12:05:00 ERROR Database timeout",
    "2024-01-01 12:05:05 ERROR Database timeout",
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
    "2024-01-01 12:09:00 WARN Memory usage at 87%",
    "2024-01-01 12:10:00 INFO User 42 logged out",
]


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    report_path: Path = Path(DEFAULT_REPORT_PATH)


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """A parsed error log event."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class ApiCall:
    """A parsed API latency event."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class LogExtract:
    """Structured data extracted from the log file."""

    error_events: list[ErrorEvent]
    api_calls: list[ApiCall]
    active_session_count: int


@dataclass(frozen=True, slots=True)
class ReportData:
    """Aggregated data used for persistence and HTML rendering."""

    error_summary: dict[str, int]
    api_latency_by_endpoint: dict[str, float]
    active_session_count: int


def run_pipeline() -> None:
    """Execute the ETL workflow for the log processing pipeline."""
    config = load_config()
    ensure_sample_log_exists(config.log_file)
    extracted = extract_log_data(config.log_file)
    report_data = transform_log_data(extracted)
    print_connection_banner(config)
    load_metrics(config.db_path, report_data)
    write_report(config.report_path, report_data)
    print(f"Job finished at {dt.datetime.now()}")


def load_config() -> Config:
    """Load required configuration from environment variables."""
    db_path = require_env("PIPELINE_DB_PATH")
    log_file = require_env("PIPELINE_LOG_FILE")
    db_host = require_env("PIPELINE_DB_HOST")
    db_port = int(require_env("PIPELINE_DB_PORT"))
    db_user = require_env("PIPELINE_DB_USER")
    db_password = require_env("PIPELINE_DB_PASSWORD")
    report_path = Path(os.getenv("PIPELINE_REPORT_PATH", DEFAULT_REPORT_PATH))
    return Config(
        db_path=Path(db_path),
        log_file=Path(log_file),
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_password=db_password,
        report_path=report_path,
    )


def require_env(name: str) -> str:
    """Return a required environment variable or raise a helpful error."""
    value = os.getenv(name)
    if value:
        return value
    raise ValueError(f"Missing required environment variable: {name}")


def ensure_sample_log_exists(log_file: Path) -> None:
    """Create a sample log file when the configured file does not exist."""
    if log_file.exists():
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("\n".join(SAMPLE_LOG_LINES) + "\n", encoding="utf-8")


def extract_log_data(log_file: Path) -> LogExtract:
    """Extract structured events and active session state from the log file."""
    error_events: list[ErrorEvent] = []
    api_calls: list[ApiCall] = []
    active_sessions: dict[str, str] = {}

    if not log_file.exists():
        return LogExtract(error_events=error_events, api_calls=api_calls, active_session_count=0)

    with log_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            parsed = parse_log_line(raw_line)
            if parsed is None:
                continue
            timestamp, level, message = parsed
            if level == "ERROR":
                error_events.append(ErrorEvent(timestamp=timestamp, message=message))
                continue
            if level == "WARN":
                continue
            update_sessions(active_sessions, timestamp, message)
            api_call = parse_api_call(timestamp, message)
            if api_call is not None:
                api_calls.append(api_call)

    return LogExtract(
        error_events=error_events,
        api_calls=api_calls,
        active_session_count=len(active_sessions),
    )


def parse_log_line(line: str) -> tuple[str, str, str] | None:
    """Parse a raw log line into timestamp, level, and message fields."""
    match = LOG_PATTERN.match(line.strip())
    if match is None:
        return None
    timestamp = match.group("timestamp")
    level = match.group("level")
    message = match.group("message") or ""
    return timestamp, level, message


def update_sessions(active_sessions: dict[str, str], timestamp: str, message: str) -> None:
    """Update active session state from a parsed user activity log message."""
    match = USER_ACTION_PATTERN.match(message)
    if match is None:
        return
    user_id = match.group("user_id")
    action = match.group("action")
    if "logged in" in action:
        active_sessions[user_id] = timestamp
        return
    if "logged out" in action:
        active_sessions.pop(user_id, None)


def parse_api_call(timestamp: str, message: str) -> ApiCall | None:
    """Parse an API latency message into a structured API call event."""
    match = API_PATTERN.match(message)
    if match is None:
        return None
    duration_ms = int(match.group("duration_ms") or "0")
    return ApiCall(
        timestamp=timestamp,
        endpoint=match.group("endpoint"),
        duration_ms=duration_ms,
    )


def transform_log_data(extracted: LogExtract) -> ReportData:
    """Aggregate extracted log data into report-ready metrics."""
    error_summary: dict[str, int] = {}
    latency_buckets: dict[str, list[int]] = {}

    for event in extracted.error_events:
        error_summary[event.message] = error_summary.get(event.message, 0) + 1

    for call in extracted.api_calls:
        latency_buckets.setdefault(call.endpoint, []).append(call.duration_ms)

    api_latency_by_endpoint = {
        endpoint: sum(values) / len(values)
        for endpoint, values in latency_buckets.items()
    }
    return ReportData(
        error_summary=error_summary,
        api_latency_by_endpoint=api_latency_by_endpoint,
        active_session_count=extracted.active_session_count,
    )


def print_connection_banner(config: Config) -> None:
    """Print the database connection banner without exposing the password."""
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")


def load_metrics(db_path: Path, report_data: ReportData) -> None:
    """Persist aggregated metrics to SQLite using parameterized queries."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    current_timestamp = dt.datetime.now().isoformat(sep=" ")

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )
        cursor.executemany(
            "INSERT INTO errors VALUES (?, ?, ?)",
            [
                (current_timestamp, message, count)
                for message, count in report_data.error_summary.items()
            ],
        )
        cursor.executemany(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            [
                (current_timestamp, endpoint, average_ms)
                for endpoint, average_ms in report_data.api_latency_by_endpoint.items()
            ],
        )


def write_report(report_path: Path, report_data: ReportData) -> None:
    """Render the HTML report with the same information as the original script."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_report_html(report_data)
    report_path.write_text(html, encoding="utf-8")


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
    for endpoint, average_ms in report_data.api_latency_by_endpoint.items():
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


if __name__ == "__main__":
    run_pipeline()
