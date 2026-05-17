"""Server log pipeline: extract, transform, and load log data into reports.

Reads a server log file, parses structured entries via regex, aggregates
metrics, persists them to SQLite (with parameterized queries), and renders
an HTML report.

Configuration is sourced from environment variables (PIPELINE_* prefix)
with sensible defaults for local development.
"""

import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration — all env-driven, no hardcoded secrets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Pipeline configuration loaded from environment variables."""

    db_path: str
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str
    report_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        """Build configuration from PIPELINE_* environment variables."""
        return cls(
            db_path=os.getenv("PIPELINE_DB_PATH", "metrics.db"),
            log_file=Path(os.getenv("PIPELINE_LOG_FILE", "server.log")),
            db_host=os.getenv("PIPELINE_DB_HOST", "localhost"),
            db_port=int(os.getenv("PIPELINE_DB_PORT", "5432")),
            db_user=os.getenv("PIPELINE_DB_USER", "admin"),
            db_pass=os.getenv("PIPELINE_DB_PASS", ""),
            report_path=Path(os.getenv("PIPELINE_REPORT_PATH", "report.html")),
        )


# ---------------------------------------------------------------------------
# Domain types — structured records replacing untyped dicts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorEntry:
    """A parsed ERROR-level log line."""

    timestamp: str
    message: str


@dataclass(frozen=True)
class UserEvent:
    """A parsed INFO User log line (login/logout)."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True)
class ApiCall:
    """A parsed INFO API log line with endpoint and response time."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class WarningEntry:
    """A parsed WARN-level log line."""

    timestamp: str
    message: str


@dataclass
class ParsedLog:
    """Container for all structured records extracted from a log file."""

    errors: list[ErrorEntry] = field(default_factory=list)
    user_events: list[UserEvent] = field(default_factory=list)
    api_calls: list[ApiCall] = field(default_factory=list)
    warnings: list[WarningEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Compiled regex patterns for log parsing
# ---------------------------------------------------------------------------

_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r" (?P<level>ERROR|INFO|WARN)"
    r" (?P<rest>.*)$"
)
_USER_EVENT_RE = re.compile(
    r"^User (?P<user_id>\S+) (?P<action>.*)$"
)
_API_CALL_RE = re.compile(
    r"^API (?P<endpoint>\S+)(?: took (?P<duration>\d+)ms)?$"
)


# ---------------------------------------------------------------------------
# Extract — parse log file into structured records
# ---------------------------------------------------------------------------


def _parse_line(line: str, parsed: ParsedLog) -> None:
    """Classify and append a single log line to the appropriate collection."""
    match = _LOG_LINE_RE.match(line)
    if not match:
        return

    timestamp, level, rest = match.group("timestamp", "level", "rest")

    if level == "ERROR":
        parsed.errors.append(ErrorEntry(timestamp=timestamp, message=rest))
        return

    if level == "WARN":
        parsed.warnings.append(WarningEntry(timestamp=timestamp, message=rest))
        return

    # level == "INFO"
    user_match = _USER_EVENT_RE.match(rest)
    if user_match:
        parsed.user_events.append(UserEvent(
            timestamp=timestamp,
            user_id=user_match.group("user_id"),
            action=user_match.group("action"),
        ))
        return

    api_match = _API_CALL_RE.match(rest)
    if api_match:
        parsed.api_calls.append(ApiCall(
            timestamp=timestamp,
            endpoint=api_match.group("endpoint"),
            duration_ms=int(api_match.group("duration") or "0"),
        ))


def extract_log_entries(log_file: Path) -> ParsedLog:
    """Read a log file and return structured records for each line."""
    parsed = ParsedLog()
    if not log_file.exists():
        return parsed

    with log_file.open() as f:
        for line in f:
            _parse_line(line.rstrip("\n"), parsed)
    return parsed


# ---------------------------------------------------------------------------
# Transform — aggregate raw records into summary data
# ---------------------------------------------------------------------------


def compute_error_summary(errors: list[ErrorEntry]) -> dict[str, int]:
    """Aggregate errors into a {message: count} summary."""
    summary: dict[str, int] = {}
    for error in errors:
        summary[error.message] = summary.get(error.message, 0) + 1
    return summary


def compute_api_latency(api_calls: list[ApiCall]) -> dict[str, list[int]]:
    """Group API response durations by endpoint."""
    stats: dict[str, list[int]] = {}
    for call in api_calls:
        stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return stats


def compute_active_sessions(user_events: list[UserEvent]) -> dict[str, str]:
    """Track currently logged-in users: {user_id: login_timestamp}."""
    sessions: dict[str, str] = {}
    for event in user_events:
        if "logged in" in event.action:
            sessions[event.user_id] = event.timestamp
        elif "logged out" in event.action and event.user_id in sessions:
            del sessions[event.user_id]
    return sessions


# ---------------------------------------------------------------------------
# Load — persist to database and render report
# ---------------------------------------------------------------------------


def load_error_metrics(conn: sqlite3.Connection, error_summary: dict[str, int]) -> None:
    """Insert error summary into the database using parameterized queries."""
    now = datetime.now().isoformat()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    for message, count in error_summary.items():
        conn.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, message, count))


def load_api_metrics(conn: sqlite3.Connection, api_latency: dict[str, list[int]]) -> None:
    """Insert API latency averages into the database using parameterized queries."""
    now = datetime.now().isoformat()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    for endpoint, times in api_latency.items():
        avg = sum(times) / len(times)
        conn.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, endpoint, avg))


def render_report(
    error_summary: dict[str, int],
    api_latency: dict[str, list[int]],
    active_sessions: dict[str, str],
) -> str:
    """Generate an HTML report from aggregated log data."""
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for message, count in error_summary.items():
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, times in api_latency.items():
        avg = round(sum(times) / len(times), 1)
        lines.append(f"<tr><td>{endpoint}</td><td>{avg}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{len(active_sessions)} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines)


def write_report(content: str, output_path: Path) -> None:
    """Write the rendered report to an HTML file."""
    output_path.write_text(content)


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


def run_pipeline(config: Config | None = None) -> None:
    """Run the full ETL pipeline: extract, transform, load."""
    if config is None:
        config = Config.from_env()

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    # Extract
    parsed = extract_log_entries(config.log_file)

    # Transform
    error_summary = compute_error_summary(parsed.errors)
    api_latency = compute_api_latency(parsed.api_calls)
    active_sessions = compute_active_sessions(parsed.user_events)

    # Load
    conn = sqlite3.connect(config.db_path)
    try:
        load_error_metrics(conn, error_summary)
        load_api_metrics(conn, api_latency)
        conn.commit()
    finally:
        conn.close()

    report = render_report(error_summary, api_latency, active_sessions)
    write_report(report, config.report_path)

    print(f"Job finished at {datetime.now()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

SAMPLE_LOG_LINES = (
    "2024-01-01 12:00:00 INFO User 42 logged in\n"
    "2024-01-01 12:05:00 ERROR Database timeout\n"
    "2024-01-01 12:05:05 ERROR Database timeout\n"
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
    "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
    "2024-01-01 12:10:00 INFO User 42 logged out\n"
)

if __name__ == "__main__":
    cfg = Config.from_env()
    if not cfg.log_file.exists():
        cfg.log_file.write_text(SAMPLE_LOG_LINES)
    run_pipeline(cfg)