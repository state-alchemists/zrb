"""Server-log ETL pipeline: extract, transform, load, and report.

Reads a server log file, aggregates errors / API latencies / sessions,
persists metrics to SQLite, and writes an HTML report.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


def load_config() -> Config:
    """Build configuration from environment variables with sensible defaults."""
    return Config(
        db_path=os.getenv("PIPELINE_DB_PATH", "metrics.db"),
        log_file=os.getenv("PIPELINE_LOG_FILE", "server.log"),
        db_host=os.getenv("PIPELINE_DB_HOST", "localhost"),
        db_port=int(os.getenv("PIPELINE_DB_PORT", "5432")),
        db_user=os.getenv("PIPELINE_DB_USER", ""),
        db_pass=os.getenv("PIPELINE_DB_PASS", ""),
    )


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ErrorEntry:
    """A single ERROR-level log line."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class WarningEntry:
    """A single WARN-level log line."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class UserEvent:
    """A user login/logout event extracted from an INFO line."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiCall:
    """An API call with latency extracted from an INFO line."""

    timestamp: str
    endpoint: str
    latency_ms: int


@dataclass
class ParsedLogs:
    """All log entries grouped by category after extraction."""

    errors: list[ErrorEntry] = field(default_factory=list)
    warnings: list[WarningEntry] = field(default_factory=list)
    user_events: list[UserEvent] = field(default_factory=list)
    api_calls: list[ApiCall] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ErrorSummary:
    """Aggregated error occurrence count."""

    message: str
    count: int


@dataclass(frozen=True, slots=True)
class ApiLatency:
    """Average latency for a single API endpoint."""

    endpoint: str
    avg_ms: float


@dataclass(frozen=True, slots=True)
class ReportData:
    """Aggregated metrics ready for persistence and reporting."""

    errors: tuple[ErrorSummary, ...]
    api_latencies: tuple[ApiLatency, ...]
    active_session_count: int


# ---------------------------------------------------------------------------
# Extract — log parsing
# ---------------------------------------------------------------------------

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR|WARN) (.*)$"
)
_USER_EVENT_RE = re.compile(r"^User (\S+) (.+)$")
_API_CALL_RE = re.compile(r"^API (\S+) took (\d+)ms$")


def _parse_log_line(line: str) -> ErrorEntry | WarningEntry | UserEvent | ApiCall | None:
    """Parse a single log line into a typed domain object.

    Returns ``None`` when the line does not match any known format.
    """
    match = _LOG_LINE_RE.match(line.strip())
    if not match:
        return None

    timestamp, level, rest = match.group(1), match.group(2), match.group(3)

    if level == "ERROR":
        return ErrorEntry(timestamp=timestamp, message=rest)
    if level == "WARN":
        return WarningEntry(timestamp=timestamp, message=rest)

    if level == "INFO":
        user_match = _USER_EVENT_RE.match(rest)
        if user_match:
            return UserEvent(
                timestamp=timestamp,
                user_id=user_match.group(1),
                action=user_match.group(2),
            )
        api_match = _API_CALL_RE.match(rest)
        if api_match:
            return ApiCall(
                timestamp=timestamp,
                endpoint=api_match.group(1),
                latency_ms=int(api_match.group(2)),
            )

    return None


def extract_log_entries(log_file: str) -> ParsedLogs:
    """Read the log file and return structured entries grouped by category."""
    logs = ParsedLogs()
    path = Path(log_file)
    if not path.exists():
        return logs

    with path.open("r") as fh:
        for line in fh:
            entry = _parse_log_line(line)
            if isinstance(entry, ErrorEntry):
                logs.errors.append(entry)
            elif isinstance(entry, WarningEntry):
                logs.warnings.append(entry)
            elif isinstance(entry, UserEvent):
                logs.user_events.append(entry)
            elif isinstance(entry, ApiCall):
                logs.api_calls.append(entry)

    return logs


# ---------------------------------------------------------------------------
# Transform — aggregation
# ---------------------------------------------------------------------------

def _compute_error_summaries(errors: list[ErrorEntry]) -> tuple[ErrorSummary, ...]:
    """Count occurrences of each distinct error message."""
    counts: dict[str, int] = {}
    for err in errors:
        counts[err.message] = counts.get(err.message, 0) + 1
    return tuple(ErrorSummary(message=msg, count=cnt) for msg, cnt in counts.items())


def _compute_api_latencies(api_calls: list[ApiCall]) -> tuple[ApiLatency, ...]:
    """Calculate average latency per API endpoint."""
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.latency_ms)
    return tuple(
        ApiLatency(endpoint=ep, avg_ms=sum(times) / len(times))
        for ep, times in endpoint_times.items()
    )


def _count_active_sessions(user_events: list[UserEvent]) -> int:
    """Track login/logout events to determine currently active sessions."""
    sessions: dict[str, str] = {}
    for event in user_events:
        if "logged in" in event.action:
            sessions[event.user_id] = event.timestamp
        elif "logged out" in event.action and event.user_id in sessions:
            del sessions[event.user_id]
    return len(sessions)


def compute_report_data(logs: ParsedLogs) -> ReportData:
    """Aggregate parsed log entries into report metrics."""
    return ReportData(
        errors=_compute_error_summaries(logs.errors),
        api_latencies=_compute_api_latencies(logs.api_calls),
        active_session_count=_count_active_sessions(logs.user_events),
    )


# ---------------------------------------------------------------------------
# Load — database persistence
# ---------------------------------------------------------------------------

def load_to_db(db_path: str, report_data: ReportData) -> None:
    """Persist report metrics to SQLite using parameterized queries."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        now = str(datetime.datetime.now())
        for err in report_data.errors:
            cursor.execute(
                "INSERT INTO errors VALUES (?, ?, ?)", (now, err.message, err.count)
            )
        for lat in report_data.api_latencies:
            cursor.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (now, lat.endpoint, lat.avg_ms),
            )

        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(report_data: ReportData, output_path: str) -> None:
    """Write the HTML report to disk."""
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err in report_data.errors:
        lines.append(f"<li><b>{err.message}</b>: {err.count} occurrences</li>")
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for lat in report_data.api_latencies:
        lines.append(f"<tr><td>{lat.endpoint}</td><td>{round(lat.avg_ms, 1)}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{report_data.active_session_count} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(output_path, "w") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full ETL pipeline: extract, transform, load, report."""
    config = load_config()
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    logs = extract_log_entries(config.log_file)
    report_data = compute_report_data(logs)
    load_to_db(config.db_path, report_data)
    generate_report(report_data, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    config = load_config()
    if not Path(config.log_file).exists():
        Path(config.log_file).write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )
    run_pipeline()