"""ETL pipeline for processing server logs and generating an HTML report.

This refactors the original `pipeline.py` script with:
- Environment-variable configuration (no hardcoded paths/credentials)
- Parameterized SQL (prevents SQL injection)
- Clear Extract → Transform → Load structure
- Regex-based log parsing
- Type hints + docstrings

Outputs `report.html` containing:
- Error summary
- API latency table
- Active session count

Environment variables:
- PIPELINE_DB_PATH: SQLite DB file path (default: metrics.db)
- PIPELINE_LOG_FILE: log file path (default: server.log)

Optional (kept for compatibility with previous script's intent; not used by SQLite):
- PIPELINE_DB_HOST (default: localhost)
- PIPELINE_DB_PORT (default: 5432)
- PIPELINE_DB_USER (default: admin)
- PIPELINE_DB_PASS (default: password123)

Run:
  python pipeline_refactored.py
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

    # Not used by sqlite3, but retained so the script no longer hardcodes credentials.
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True)
class LogEvent:
    """A parsed log event."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class ApiCall:
    """A parsed API call metric."""

    timestamp: str
    endpoint: str
    duration_ms: int


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from environment variables."""

    e = os.environ if env is None else env

    def _get(name: str, default: str) -> str:
        value = e.get(name, default)
        return value

    def _get_int(name: str, default: int) -> int:
        raw = e.get(name)
        if raw is None or raw.strip() == "":
            return default
        return int(raw)

    return Config(
        db_path=_get("PIPELINE_DB_PATH", "metrics.db"),
        log_file=_get("PIPELINE_LOG_FILE", "server.log"),
        db_host=_get("PIPELINE_DB_HOST", "localhost"),
        db_port=_get_int("PIPELINE_DB_PORT", 5432),
        db_user=_get("PIPELINE_DB_USER", "admin"),
        db_pass=_get("PIPELINE_DB_PASS", "password123"),
    )


_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|WARN|ERROR)\s+"
    r"(?P<message>.*)$"
)

_USER_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
_API_RE = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+.*?\s+took\s+(?P<ms>\d+)ms)?\s*$")


def extract_log_lines(log_file: str) -> Iterable[str]:
    """Yield log lines from `log_file` if it exists."""

    if not os.path.exists(log_file):
        return

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


def parse_log_line(line: str) -> Optional[LogEvent]:
    """Parse a single log line using regex.

    Expected format:
      YYYY-MM-DD HH:MM:SS LEVEL message...
    """

    m = _LOG_LINE_RE.match(line)
    if not m:
        return None

    timestamp = f"{m.group('date')} {m.group('time')}"
    return LogEvent(timestamp=timestamp, level=m.group("level"), message=m.group("message"))


def extract_events(log_lines: Iterable[str]) -> Tuple[List[LogEvent], List[ApiCall], Dict[str, str]]:
    """Extract structured events, API calls, and active session map from log lines."""

    events: List[LogEvent] = []
    api_calls: List[ApiCall] = []
    sessions: Dict[str, str] = {}

    for raw in log_lines:
        evt = parse_log_line(raw)
        if evt is None:
            continue

        if evt.level == "INFO":
            user_m = _USER_RE.match(evt.message)
            if user_m:
                uid = user_m.group("uid")
                action = user_m.group("action").strip()
                if "logged in" in action:
                    sessions[uid] = evt.timestamp
                elif "logged out" in action:
                    sessions.pop(uid, None)

                events.append(LogEvent(timestamp=evt.timestamp, level="INFO", message=f"User {uid} {action}"))
                continue

            api_m = _API_RE.match(evt.message)
            if api_m:
                endpoint = api_m.group("endpoint")
                ms_raw = api_m.group("ms")
                duration_ms = int(ms_raw) if ms_raw is not None else 0
                api_calls.append(ApiCall(timestamp=evt.timestamp, endpoint=endpoint, duration_ms=duration_ms))
                events.append(evt)
                continue

            events.append(evt)
            continue

        events.append(evt)

    return events, api_calls, sessions


def transform_error_summary(events: Sequence[LogEvent]) -> Dict[str, int]:
    """Compute error counts keyed by error message."""

    summary: Dict[str, int] = {}
    for evt in events:
        if evt.level == "ERROR":
            summary[evt.message] = summary.get(evt.message, 0) + 1
    return summary


def transform_api_latency(api_calls: Sequence[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""

    by_endpoint: Dict[str, List[int]] = {}
    for call in api_calls:
        by_endpoint.setdefault(call.endpoint, []).append(call.duration_ms)
    return by_endpoint


def _connect_sqlite(db_path: str) -> sqlite3.Connection:
    """Connect to SQLite database."""

    return sqlite3.connect(db_path)


def load_metrics_to_db(
    conn: sqlite3.Connection,
    *,
    now: dt.datetime,
    error_summary: Mapping[str, int],
    api_latency: Mapping[str, Sequence[int]],
) -> None:
    """Load aggregated metrics into the database using parameterized queries."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    now_str = str(now)

    for msg, count in error_summary.items():
        cur.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_str, msg, int(count)),
        )

    for endpoint, times in api_latency.items():
        if not times:
            continue
        avg = sum(times) / len(times)
        cur.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_str, endpoint, float(avg)),
        )

    conn.commit()


def render_report_html(
    *,
    error_summary: Mapping[str, int],
    api_latency: Mapping[str, Sequence[int]],
    active_sessions: Mapping[str, str],
) -> str:
    """Render the HTML report (same information as the original script)."""

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"

    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, times in api_latency.items():
        if not times:
            avg = 0.0
        else:
            avg = sum(times) / len(times)
        out += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"

    out += "</body>\n</html>"
    return out


def write_report(path: str, html: str) -> None:
    """Write report HTML to disk."""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def ensure_sample_log_exists(log_file: str) -> None:
    """Create a small sample log file if none exists (keeps original behavior)."""

    if os.path.exists(log_file):
        return

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def run_pipeline(cfg: Config) -> None:
    """Run Extract → Transform → Load and generate `report.html`."""

    print(f"Connecting to {cfg.db_host}:{cfg.db_port} as {cfg.db_user}...")

    ensure_sample_log_exists(cfg.log_file)

    # Extract
    log_lines = extract_log_lines(cfg.log_file)
    events, api_calls, sessions = extract_events(log_lines)

    # Transform
    error_summary = transform_error_summary(events)
    api_latency = transform_api_latency(api_calls)

    # Load
    now = dt.datetime.now()
    conn = _connect_sqlite(cfg.db_path)
    try:
        load_metrics_to_db(conn, now=now, error_summary=error_summary, api_latency=api_latency)
    finally:
        conn.close()

    # Report
    html = render_report_html(
        error_summary=error_summary,
        api_latency=api_latency,
        active_sessions=sessions,
    )
    write_report("report.html", html)

    print(f"Job finished at {dt.datetime.now()}")


def main() -> None:
    """CLI entrypoint."""

    cfg = load_config()
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
