import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>ERROR|INFO|WARN) (?P<message>.*)$"
)
USER_ACTION_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?: took (?P<duration_ms>\d+)ms)?$")


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: str
    log_file_path: str
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    report_path: str = "report.html"


@dataclass(frozen=True)
class ErrorRecord:
    """Represents a parsed error log entry."""

    timestamp: str
    message: str


@dataclass(frozen=True)
class ApiCall:
    """Represents a parsed API call log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class UserEvent:
    """Represents a parsed user session event."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True)
class ParsedLogData:
    """Structured log data extracted from the server log."""

    errors: List[ErrorRecord]
    api_calls: List[ApiCall]
    user_events: List[UserEvent]
    warnings: List[str]
    active_sessions: Dict[str, str]


@dataclass(frozen=True)
class ReportData:
    """Aggregated data used for database storage and HTML report generation."""

    error_summary: Dict[str, int]
    endpoint_stats: Dict[str, float]
    active_session_count: int


def get_env(name: str, default: str | None = None) -> str:
    """Return an environment variable value or raise if it is missing."""

    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    """Load runtime configuration from environment variables."""

    return Config(
        db_path=get_env("DB_PATH", "metrics.db"),
        log_file_path=get_env("LOG_FILE_PATH", "server.log"),
        db_host=get_env("DB_HOST", "localhost"),
        db_port=int(get_env("DB_PORT", "5432")),
        db_user=get_env("DB_USER", "admin"),
        db_password=get_env("DB_PASSWORD", "password123"),
        report_path=get_env("REPORT_PATH", "report.html"),
    )


def ensure_sample_log_exists(log_file_path: str) -> None:
    """Create a sample log file when the expected log file does not exist."""

    if os.path.exists(log_file_path):
        return

    with open(log_file_path, "w", encoding="utf-8") as file_handle:
        file_handle.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        file_handle.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        file_handle.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        file_handle.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        file_handle.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        file_handle.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def extract_log_data(log_file_path: str) -> ParsedLogData:
    """Extract structured records from the log file using regex parsing."""

    errors: List[ErrorRecord] = []
    api_calls: List[ApiCall] = []
    user_events: List[UserEvent] = []
    warnings: List[str] = []
    active_sessions: Dict[str, str] = {}

    if not os.path.exists(log_file_path):
        return ParsedLogData(errors, api_calls, user_events, warnings, active_sessions)

    with open(log_file_path, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            parsed = parse_log_line(line.strip())
            if parsed is None:
                continue

            record_type, record = parsed
            if record_type == "error":
                errors.append(record)
            elif record_type == "api":
                api_calls.append(record)
            elif record_type == "user":
                user_events.append(record)
                if "logged in" in record.action:
                    active_sessions[record.user_id] = record.timestamp
                elif "logged out" in record.action:
                    active_sessions.pop(record.user_id, None)
            elif record_type == "warn":
                warnings.append(record)

    return ParsedLogData(errors, api_calls, user_events, warnings, active_sessions)


def parse_log_line(line: str) -> tuple[str, ErrorRecord | ApiCall | UserEvent | str] | None:
    """Parse a single log line into a typed record."""

    match = LOG_PATTERN.match(line)
    if match is None:
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    message = match.group("message")

    if level == "ERROR":
        return "error", ErrorRecord(timestamp=timestamp, message=message)

    if level == "WARN":
        return "warn", message

    user_match = USER_ACTION_PATTERN.match(message)
    if user_match is not None:
        return (
            "user",
            UserEvent(
                timestamp=timestamp,
                user_id=user_match.group("user_id"),
                action=user_match.group("action"),
            ),
        )

    api_match = API_PATTERN.match(message)
    if api_match is not None:
        duration_ms = int(api_match.group("duration_ms") or "0")
        return (
            "api",
            ApiCall(
                timestamp=timestamp,
                endpoint=api_match.group("endpoint"),
                duration_ms=duration_ms,
            ),
        )

    return None


def transform_log_data(parsed_data: ParsedLogData) -> ReportData:
    """Aggregate extracted log data into report-ready metrics."""

    error_summary: Dict[str, int] = {}
    for error in parsed_data.errors:
        error_summary[error.message] = error_summary.get(error.message, 0) + 1

    endpoint_durations: Dict[str, List[int]] = {}
    for call in parsed_data.api_calls:
        endpoint_durations.setdefault(call.endpoint, []).append(call.duration_ms)

    endpoint_stats = {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in endpoint_durations.items()
    }

    return ReportData(
        error_summary=error_summary,
        endpoint_stats=endpoint_stats,
        active_session_count=len(parsed_data.active_sessions),
    )


def load_metrics(report_data: ReportData, db_path: str) -> None:
    """Persist aggregated metrics to SQLite using parameterized queries."""

    now = dt.datetime.now().isoformat(sep=" ")
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
            [
                (now, endpoint, average_ms)
                for endpoint, average_ms in report_data.endpoint_stats.items()
            ],
        )
        connection.commit()


def render_report(report_data: ReportData) -> str:
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

    for endpoint, average_ms in report_data.endpoint_stats.items():
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


def write_report(report_html: str, report_path: str) -> None:
    """Write the generated HTML report to disk."""

    with open(report_path, "w", encoding="utf-8") as file_handle:
        file_handle.write(report_html)


def run_pipeline() -> None:
    """Execute the extract, transform, and load pipeline and generate the report."""

    config = load_config()
    ensure_sample_log_exists(config.log_file_path)
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")
    extracted_data = extract_log_data(config.log_file_path)
    report_data = transform_log_data(extracted_data)
    load_metrics(report_data, config.db_path)
    write_report(render_report(report_data), config.report_path)
    print(f"Job finished at {dt.datetime.now()}")


if __name__ == "__main__":
    run_pipeline()
