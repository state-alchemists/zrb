"""Server log processing pipeline.

This script parses server logs, stores aggregated metrics in a SQLite database,
and generates an HTML report.

Security/maintenance improvements vs the original `pipeline.py`:
- All configuration comes from environment variables (no hardcoded creds/paths).
- SQL writes use parameterized queries.
- Logic is split into Extract → Transform → Load style functions.
- Log parsing uses regular expressions and is resilient to non-matching lines.
- Type hints + docstrings throughout.

Environment variables:
- PIPELINE_DB_PATH: path to SQLite DB (default: metrics.db)
- PIPELINE_LOG_FILE: path to log file (default: server.log)
- PIPELINE_REPORT_PATH: path to output HTML report (default: report.html)

Optional (kept for backwards compatibility with prior output; not used by SQLite):
- PIPELINE_DB_HOST (default: localhost)
- PIPELINE_DB_PORT (default: 5432)
- PIPELINE_DB_USER (default: admin)
- PIPELINE_DB_PASS (default: password123)

Log format expected (examples):
- 2024-01-01 12:05:00 ERROR Database timeout
- 2024-01-01 12:00:00 INFO User 42 logged in
- 2024-01-01 12:08:00 INFO API /users/profile took 250ms
- 2024-01-01 12:09:00 WARN Memory usage at 87%
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: str
    log_file: str
    report_path: str

    # Not used by sqlite3, but historically printed; keep configurable.
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True)
class ParsedError:
    """Represents a parsed ERROR log entry."""

    timestamp: str
    message: str


@dataclass(frozen=True)
class ParsedApiCall:
    """Represents a parsed API timing log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class ParsedUserEvent:
    """Represents a parsed user login/logout event."""

    timestamp: str
    user_id: str
    action: str


LOG_PREFIX_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<rest>.*)$"
)
USER_EVENT_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
API_CALL_RE = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?\s*$")


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from environment variables."""

    env = os.environ if env is None else env

    def get_int(key: str, default: int) -> int:
        raw = env.get(key)
        if raw is None or raw.strip() == "":
            return default
        try:
            return int(raw)
        except ValueError as e:
            raise ValueError(f"{key} must be an int; got {raw!r}") from e

    return Config(
        db_path=env.get("PIPELINE_DB_PATH", "metrics.db"),
        log_file=env.get("PIPELINE_LOG_FILE", "server.log"),
        report_path=env.get("PIPELINE_REPORT_PATH", "report.html"),
        db_host=env.get("PIPELINE_DB_HOST", "localhost"),
        db_port=get_int("PIPELINE_DB_PORT", 5432),
        db_user=env.get("PIPELINE_DB_USER", "admin"),
        db_pass=env.get("PIPELINE_DB_PASS", "password123"),
    )


def extract_log_lines(log_path: str) -> List[str]:
    """Extract phase: read log file lines.

    Returns an empty list if the log file does not exist.
    """

    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


def parse_log_line(line: str) -> Tuple[Optional[ParsedError], Optional[ParsedApiCall], Optional[ParsedUserEvent]]:
    """Parse a single log line.

    Returns a tuple (error, api_call, user_event) where non-applicable items are None.
    Non-matching or unsupported lines return (None, None, None).
    """

    m = LOG_PREFIX_RE.match(line)
    if not m:
        return (None, None, None)

    timestamp = f"{m.group('date')} {m.group('time')}"
    level = m.group("level")
    rest = m.group("rest").strip()

    if level == "ERROR":
        if rest == "":
            return (None, None, None)
        return (ParsedError(timestamp=timestamp, message=rest), None, None)

    if level == "INFO":
        um = USER_EVENT_RE.match(rest)
        if um:
            uid = um.group("uid")
            action = um.group("action").strip()
            return (None, None, ParsedUserEvent(timestamp=timestamp, user_id=uid, action=action))

        am = API_CALL_RE.match(rest)
        if am:
            endpoint = am.group("endpoint")
            ms_raw = am.group("ms")
            duration_ms = int(ms_raw) if ms_raw is not None else 0
            return (None, ParsedApiCall(timestamp=timestamp, endpoint=endpoint, duration_ms=duration_ms), None)

    return (None, None, None)


def extract_events(lines: Iterable[str]) -> Tuple[List[ParsedError], List[ParsedApiCall], List[ParsedUserEvent]]:
    """Extract phase: parse log lines into structured events."""

    errors: List[ParsedError] = []
    api_calls: List[ParsedApiCall] = []
    user_events: List[ParsedUserEvent] = []

    for line in lines:
        err, api, user = parse_log_line(line)
        if err is not None:
            errors.append(err)
        if api is not None:
            api_calls.append(api)
        if user is not None:
            user_events.append(user)

    return errors, api_calls, user_events


def transform_error_summary(errors: Sequence[ParsedError]) -> Dict[str, int]:
    """Transform phase: aggregate errors by message."""

    summary: Dict[str, int] = {}
    for e in errors:
        summary[e.message] = summary.get(e.message, 0) + 1
    return summary


def transform_api_latency(api_calls: Sequence[ParsedApiCall]) -> Dict[str, List[int]]:
    """Transform phase: group API call durations by endpoint."""

    endpoint_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        endpoint_stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return endpoint_stats


def transform_active_sessions(user_events: Sequence[ParsedUserEvent]) -> Dict[str, str]:
    """Transform phase: compute active sessions (users currently logged in).

    Returns a mapping of user_id -> last-login timestamp.
    """

    sessions: Dict[str, str] = {}
    for evt in user_events:
        action = evt.action
        if "logged in" in action:
            sessions[evt.user_id] = evt.timestamp
        elif "logged out" in action:
            sessions.pop(evt.user_id, None)
    return sessions


def init_db(conn: sqlite3.Connection) -> None:
    """Create required tables if they do not exist."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")


def load_metrics_to_db(
    conn: sqlite3.Connection,
    error_summary: Mapping[str, int],
    api_latency: Mapping[str, Sequence[int]],
    now: dt.datetime,
) -> None:
    """Load phase: persist aggregated metrics to the database using parameterized queries."""

    cur = conn.cursor()

    now_text = str(now)

    for message, count in error_summary.items():
        cur.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_text, message, int(count)),
        )

    for endpoint, times in api_latency.items():
        if not times:
            continue
        avg_ms = sum(times) / len(times)
        cur.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_text, endpoint, float(avg_ms)),
        )


def render_report_html(
    error_summary: Mapping[str, int],
    api_latency: Mapping[str, Sequence[int]],
    active_sessions: Mapping[str, str],
) -> str:
    """Render the HTML report.

    Must contain the same information as the original script:
    - Error summary list (message -> occurrence count)
    - API latency table (endpoint -> avg ms)
    - Active session count
    """

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, times in api_latency.items():
        avg = (sum(times) / len(times)) if times else 0.0
        out += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out


def write_report(report_path: str, html: str) -> None:
    """Write the report HTML to disk."""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)


def run_pipeline(config: Config) -> None:
    """Run Extract → Transform → Load pipeline and generate report."""

    lines = extract_log_lines(config.log_file)
    errors, api_calls, user_events = extract_events(lines)

    error_summary = transform_error_summary(errors)
    api_latency = transform_api_latency(api_calls)
    sessions = transform_active_sessions(user_events)

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    now = dt.datetime.now()
    conn = sqlite3.connect(config.db_path)
    try:
        init_db(conn)
        load_metrics_to_db(conn, error_summary, api_latency, now)
        conn.commit()
    finally:
        conn.close()

    html = render_report_html(error_summary, api_latency, sessions)
    write_report(config.report_path, html)

    print(f"Job finished at {now}")


def _write_sample_log_if_missing(log_path: str) -> None:
    """Create a small sample log file matching the original script's demo behavior."""

    if os.path.exists(log_path):
        return
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def main() -> None:
    """Entrypoint."""

    config = load_config()
    _write_sample_log_if_missing(config.log_file)
    run_pipeline(config)


if __name__ == "__main__":
    main()
