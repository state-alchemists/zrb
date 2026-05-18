"""Server-log processing pipeline.

Extracts structured data from server logs, transforms it into aggregate
metrics, and loads the results into a SQLite database and an HTML report.

Configuration is read from environment variables with sensible defaults.
All database operations use parameterized queries to prevent injection.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables.

    Environment variables and defaults:
        LOG_FILE   – path to the server log         (default: server.log)
        DB_PATH    – path to the SQLite database     (default: metrics.db)
        DB_HOST    – database host (logged, not used by sqlite) (default: localhost)
        DB_PORT    – database port (logged, not used by sqlite) (default: 5432)
        DB_USER    – database user (logged, not used by sqlite) (default: admin)
        DB_PASS    – database password (logged, not used by sqlite) (default: password123)
        REPORT_PATH – path for the HTML report      (default: report.html)
    """

    log_file: Path = field(default_factory=lambda: Path(os.getenv("LOG_FILE", "server.log")))
    db_path: Path = field(default_factory=lambda: Path(os.getenv("DB_PATH", "metrics.db")))
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "admin"))
    db_pass: str = field(default_factory=lambda: os.getenv("DB_PASS", "password123"))
    report_path: Path = field(default_factory=lambda: Path(os.getenv("REPORT_PATH", "report.html")))


# ---------------------------------------------------------------------------
# Structured log-event types
# ---------------------------------------------------------------------------


class ErrorEvent(NamedTuple):
    """An ERROR-level log entry."""

    timestamp: str
    message: str


class UserEvent(NamedTuple):
    """An INFO-level user action (login / logout)."""

    timestamp: str
    user_id: str
    action: str


class ApiCall(NamedTuple):
    """An INFO-level API call with latency measurement."""

    timestamp: str
    endpoint: str
    latency_ms: int


class WarnEvent(NamedTuple):
    """A WARN-level log entry."""

    timestamp: str
    message: str


@dataclass
class ParsedLog:
    """Container for all events extracted from a log file."""

    errors: list[ErrorEvent] = field(default_factory=list)
    user_events: list[UserEvent] = field(default_factory=list)
    api_calls: list[ApiCall] = field(default_factory=list)
    warnings: list[WarnEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regex patterns for log parsing
# ---------------------------------------------------------------------------

# Expected log format:
#   2024-01-01 12:00:00 INFO User 42 logged in
#   2024-01-01 12:05:00 ERROR Database timeout
#   2024-01-01 12:08:00 INFO API /users/profile took 250ms
#   2024-01-01 12:09:00 WARN Memory usage at 87%

_RE_LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<rest>.*)$"
)

_RE_USER_EVENT = re.compile(
    r"^User\s+(?P<user_id>\S+)\s+(?P<action>.*)$"
)

_RE_API_CALL = re.compile(
    r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<latency>\d+)ms)?$"
)


# ---------------------------------------------------------------------------
# Extract: parse log file
# ---------------------------------------------------------------------------


def parse_log_line(line: str) -> ErrorEvent | UserEvent | ApiCall | WarnEvent | None:
    """Parse a single log line into a structured event.

    Returns ``None`` for lines that don't match the expected format.
    """
    match = _RE_LOG_LINE.match(line)
    if not match:
        return None

    timestamp = match.group("ts")
    level = match.group("level")
    rest = match.group("rest")

    if level == "ERROR":
        return ErrorEvent(timestamp=timestamp, message=rest)

    if level == "WARN":
        return WarnEvent(timestamp=timestamp, message=rest)

    if level == "INFO":
        user_match = _RE_USER_EVENT.match(rest)
        if user_match:
            return UserEvent(
                timestamp=timestamp,
                user_id=user_match.group("user_id"),
                action=user_match.group("action"),
            )

        api_match = _RE_API_CALL.match(rest)
        if api_match:
            return ApiCall(
                timestamp=timestamp,
                endpoint=api_match.group("endpoint"),
                latency_ms=int(api_match.group("latency") or 0),
            )

    return None


def extract_log_events(log_path: Path) -> ParsedLog:
    """Read *log_path* and return all parsed events grouped by type.

    Raises ``FileNotFoundError`` if the log file does not exist.
    """
    parsed = ParsedLog()
    with log_path.open("r") as fh:
        for line in fh:
            event = parse_log_line(line)
            if isinstance(event, ErrorEvent):
                parsed.errors.append(event)
            elif isinstance(event, UserEvent):
                parsed.user_events.append(event)
            elif isinstance(event, ApiCall):
                parsed.api_calls.append(event)
            elif isinstance(event, WarnEvent):
                parsed.warnings.append(event)
    return parsed


# ---------------------------------------------------------------------------
# Transform: compute aggregates
# ---------------------------------------------------------------------------

def aggregate_errors(errors: list[ErrorEvent]) -> dict[str, int]:
    """Return a mapping of error message → occurrence count."""
    counts: dict[str, int] = {}
    for err in errors:
        counts[err.message] = counts.get(err.message, 0) + 1
    return counts


def compute_endpoint_latency(api_calls: list[ApiCall]) -> dict[str, float]:
    """Return a mapping of endpoint → average latency in ms (rounded to 1 decimal)."""
    buckets: dict[str, list[int]] = {}
    for call in api_calls:
        buckets.setdefault(call.endpoint, []).append(call.latency_ms)

    return {
        endpoint: round(sum(times) / len(times), 1)
        for endpoint, times in buckets.items()
    }


def count_active_sessions(user_events: list[UserEvent]) -> int:
    """Return the number of sessions that remain active after processing all events.

    A session is active when a "logged in" event has no matching "logged out"
    event for the same user.
    """
    active: set[str] = set()
    for evt in user_events:
        if "logged in" in evt.action:
            active.add(evt.user_id)
        elif "logged out" in evt.action:
            active.discard(evt.user_id)
    return len(active)


# ---------------------------------------------------------------------------
# Load: persist to database
# ---------------------------------------------------------------------------


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't already exist."""
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def persist_to_db(
    db_path: Path,
    error_counts: dict[str, int],
    endpoint_latency: dict[str, float],
) -> None:
    """Insert aggregated metrics into the SQLite database at *db_path*.

    Uses parameterized queries to prevent SQL injection.
    """
    now = str(datetime.datetime.now())
    conn = sqlite3.connect(db_path)
    try:
        _init_schema(conn)
        cur = conn.cursor()

        for message, count in error_counts.items():
            cur.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, message, count),
            )

        for endpoint, avg_ms in endpoint_latency.items():
            cur.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, endpoint, avg_ms),
            )

        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Load: generate HTML report
# ---------------------------------------------------------------------------


def generate_report(
    error_counts: dict[str, int],
    endpoint_latency: dict[str, float],
    active_sessions: int,
) -> str:
    """Build the HTML report string from aggregated metrics."""
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in error_counts.items():
        lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")

    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for endpoint, avg_ms in endpoint_latency.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{avg_ms}</td></tr>")

    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_sessions} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    return "\n".join(lines)


def write_report(report_path: Path, html: str) -> None:
    """Write *html* content to *report_path*."""
    report_path.write_text(html)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(config: Config | None = None) -> None:
    """Execute the full Extract → Transform → Load pipeline.

    1. **Extract** – parse the log file into structured events.
    2. **Transform** – aggregate errors, compute latency averages, count sessions.
    3. **Load** – persist metrics to SQLite and write the HTML report.
    """
    if config is None:
        config = Config()

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    # -- Extract --
    parsed = extract_log_events(config.log_file)

    # -- Transform --
    error_counts = aggregate_errors(parsed.errors)
    endpoint_latency = compute_endpoint_latency(parsed.api_calls)
    active_sessions = count_active_sessions(parsed.user_events)

    # -- Load --
    persist_to_db(config.db_path, error_counts, endpoint_latency)
    html = generate_report(error_counts, endpoint_latency, active_sessions)
    write_report(config.report_path, html)

    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Sample log generation (mirrors original script convenience)
# ---------------------------------------------------------------------------

_SAMPLE_LINES = [
    "2024-01-01 12:00:00 INFO User 42 logged in\n",
    "2024-01-01 12:05:00 ERROR Database timeout\n",
    "2024-01-01 12:05:05 ERROR Database timeout\n",
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
    "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
    "2024-01-01 12:10:00 INFO User 42 logged out\n",
]


def _ensure_sample_log(path: Path) -> None:
    """Create a sample log file if one doesn't already exist."""
    if not path.exists():
        path.write_text("".join(_SAMPLE_LINES))


if __name__ == "__main__":
    cfg = Config()
    _ensure_sample_log(cfg.log_file)
    run_pipeline(cfg)