"""Log processing pipeline (Extract → Transform → Load).

This script parses server logs, stores aggregated metrics in SQLite, and generates
an HTML report.

Configuration is provided exclusively via environment variables:

- PIPELINE_DB_PATH: Path to SQLite DB file (default: "metrics.db")
- PIPELINE_LOG_FILE: Path to log file (default: "server.log")
- PIPELINE_REPORT_PATH: Output HTML report path (default: "report.html")

Optional (for compatibility with the previous script's printed banner only; not
used by sqlite3):
- PIPELINE_DB_HOST (default: "localhost")
- PIPELINE_DB_PORT (default: "5432")
- PIPELINE_DB_USER (default: "admin")
- PIPELINE_DB_PASS (default: "")

The generated report contains:
- Error summary
- API latency table (average per endpoint)
- Active session count
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import os
import re
import sqlite3
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclasses.dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: str
    log_file: str
    report_path: str

    # Only used for printing a connection banner to preserve prior output shape.
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclasses.dataclass(frozen=True)
class ErrorEvent:
    """Represents a single error log event."""

    timestamp: str
    message: str


@dataclasses.dataclass(frozen=True)
class ApiCallEvent:
    """Represents a single API call log event."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclasses.dataclass(frozen=True)
class UserEvent:
    """Represents a user session event (login/logout)."""

    timestamp: str
    user_id: str
    action: str


@dataclasses.dataclass(frozen=True)
class ParsedLogs:
    """Container for parsed log artifacts used downstream."""

    errors: List[ErrorEvent]
    api_calls: List[ApiCallEvent]
    user_events: List[UserEvent]
    active_sessions: Mapping[str, str]


# Example line formats produced by the original script:
# 2024-01-01 12:05:00 ERROR Database timeout
# 2024-01-01 12:08:00 INFO API /users/profile took 250ms
# 2024-01-01 12:00:00 INFO User 42 logged in
# 2024-01-01 12:09:00 WARN Memory usage at 87%
_LOG_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<message>.*)$"
)

_USER_RE = re.compile(r"^User\s+(?P<user_id>\S+)\s+(?P<action>.*)$")
_API_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?$"
)


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from environment variables."""

    environ = os.environ if env is None else env

    db_path = environ.get("PIPELINE_DB_PATH", "metrics.db")
    log_file = environ.get("PIPELINE_LOG_FILE", "server.log")
    report_path = environ.get("PIPELINE_REPORT_PATH", "report.html")

    db_host = environ.get("PIPELINE_DB_HOST", "localhost")
    db_port_raw = environ.get("PIPELINE_DB_PORT", "5432")
    db_user = environ.get("PIPELINE_DB_USER", "admin")
    db_pass = environ.get("PIPELINE_DB_PASS", "")

    try:
        db_port = int(db_port_raw)
    except ValueError:
        db_port = 5432

    return Config(
        db_path=db_path,
        log_file=log_file,
        report_path=report_path,
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_pass=db_pass,
    )


def extract_lines(log_path: str) -> Iterable[str]:
    """Extract raw lines from the log file if it exists."""

    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8") as f:
        return list(f)


def _parse_timestamp(date_part: str, time_part: str) -> str:
    # Preserve the original script's timestamp string shape.
    return f"{date_part} {time_part}"


def parse_log_lines(lines: Iterable[str]) -> ParsedLogs:
    """Transform raw log lines into structured events.

    Uses regex parsing to make line handling more robust than ad-hoc splitting.
    """

    errors: List[ErrorEvent] = []
    api_calls: List[ApiCallEvent] = []
    user_events: List[UserEvent] = []
    active_sessions: Dict[str, str] = {}

    for raw in lines:
        line = raw.strip("\n")
        m = _LOG_RE.match(line)
        if not m:
            continue

        timestamp = _parse_timestamp(m.group("date"), m.group("time"))
        level = m.group("level")
        message = m.group("message").strip()

        if level == "ERROR":
            errors.append(ErrorEvent(timestamp=timestamp, message=message))
            continue

        if level == "WARN":
            # WARN events aren't currently used in the report, but keeping parsing
            # consistent makes future expansion easier.
            continue

        if level != "INFO":
            continue

        user_match = _USER_RE.match(message)
        if user_match:
            user_id = user_match.group("user_id")
            action = user_match.group("action").strip()

            if "logged in" in action:
                active_sessions[user_id] = timestamp
            elif "logged out" in action:
                active_sessions.pop(user_id, None)

            user_events.append(UserEvent(timestamp=timestamp, user_id=user_id, action=action))
            continue

        api_match = _API_RE.match(message)
        if api_match:
            endpoint = api_match.group("endpoint")
            ms_raw = api_match.group("ms")
            duration_ms = int(ms_raw) if ms_raw is not None else 0
            api_calls.append(
                ApiCallEvent(timestamp=timestamp, endpoint=endpoint, duration_ms=duration_ms)
            )

    return ParsedLogs(
        errors=errors,
        api_calls=api_calls,
        user_events=user_events,
        active_sessions=active_sessions,
    )


def aggregate_error_counts(errors: Sequence[ErrorEvent]) -> Dict[str, int]:
    """Aggregate errors by message into counts."""

    counts: Dict[str, int] = {}
    for e in errors:
        counts[e.message] = counts.get(e.message, 0) + 1
    return counts


def aggregate_api_latency(api_calls: Sequence[ApiCallEvent]) -> Dict[str, float]:
    """Compute average latency (ms) per endpoint."""

    times: DefaultDict[str, List[int]] = defaultdict(list)
    for call in api_calls:
        times[call.endpoint].append(call.duration_ms)

    return {ep: (sum(vals) / len(vals)) for ep, vals in times.items() if vals}


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def load_metrics(
    conn: sqlite3.Connection,
    error_counts: Mapping[str, int],
    api_avgs: Mapping[str, float],
    now: dt.datetime,
) -> None:
    """Load aggregated metrics into the database using parameterized queries."""

    cur = conn.cursor()
    now_str = str(now)

    cur.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now_str, msg, int(count)) for msg, count in error_counts.items()],
    )

    cur.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now_str, ep, float(avg)) for ep, avg in api_avgs.items()],
    )


def render_report_html(
    error_counts: Mapping[str, int],
    api_avgs: Mapping[str, float],
    active_session_count: int,
) -> str:
    """Render the HTML report.

    The report content matches the original script's information:
    - Error summary list
    - API latency table
    - Active session count
    """

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_avgs.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_session_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out


def write_report(path: str, html: str) -> None:
    """Write the report HTML to disk."""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def ensure_sample_log_exists(log_path: str) -> None:
    """Create a sample log file if none exists (keeps original demo behavior)."""

    if os.path.exists(log_path):
        return

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def run_pipeline(cfg: Config) -> None:
    """Run the full Extract → Transform → Load pipeline and generate the report."""

    ensure_sample_log_exists(cfg.log_file)

    # Extract
    lines = extract_lines(cfg.log_file)

    # Transform
    parsed = parse_log_lines(lines)
    error_counts = aggregate_error_counts(parsed.errors)
    api_avgs = aggregate_api_latency(parsed.api_calls)

    # Load
    print(f"Connecting to {cfg.db_host}:{cfg.db_port} as {cfg.db_user}...")
    conn = sqlite3.connect(cfg.db_path)
    try:
        init_db(conn)
        load_metrics(conn, error_counts=error_counts, api_avgs=api_avgs, now=dt.datetime.now())
        conn.commit()
    finally:
        conn.close()

    # Report
    html = render_report_html(
        error_counts=error_counts,
        api_avgs=api_avgs,
        active_session_count=len(parsed.active_sessions),
    )
    write_report(cfg.report_path, html)

    print(f"Job finished at {dt.datetime.now()}")


def main() -> None:
    """CLI entrypoint."""

    cfg = load_config()
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
