"""Log processing pipeline (Extract → Transform → Load).

This module reads a server log, computes summary metrics, stores aggregated metrics
in SQLite, and generates an HTML report.

Security and maintainability improvements over `pipeline.py`:
- All configuration is read from environment variables.
- SQL is executed using parameterized queries.
- Log parsing uses regular expressions (less fragile than string splitting).
- Code is decomposed into small, well-named functions with type hints.

Environment variables:
- PIPELINE_DB_PATH (required): path to the SQLite database file.
- PIPELINE_LOG_FILE (required): path to the server log file.
- PIPELINE_REPORT_PATH (optional): output HTML path (default: "report.html").
- PIPELINE_DB_HOST / PIPELINE_DB_PORT / PIPELINE_DB_USER / PIPELINE_DB_PASS (optional):
  accepted for compatibility with the original script's printed message.

Note: This pipeline still uses SQLite like the original; host/port/user/pass are not
used to connect, but are kept to avoid changing console output semantics.
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

    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True)
class LogError:
    timestamp: str
    message: str


@dataclass(frozen=True)
class ApiCall:
    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class UserEvent:
    timestamp: str
    user_id: str
    action: str


# Example: "2024-01-01 12:05:05 ERROR Database timeout"
_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|WARN|ERROR)\s+(?P<message>.*)$"
)

# Example: "User 42 logged in" / "User 42 logged out"
_USER_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")

# Example: "API /users/profile took 250ms"
_API_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+)(?:\s+.*?\s+)?took\s+(?P<ms>\d+)ms$"
)


def load_config(env: Mapping[str, str] = os.environ) -> Config:
    """Load configuration from environment variables.

    Raises:
        ValueError: if required environment variables are missing.
    """

    db_path = env.get("PIPELINE_DB_PATH")
    log_file = env.get("PIPELINE_LOG_FILE")
    report_path = env.get("PIPELINE_REPORT_PATH", "report.html")

    missing: List[str] = []
    if not db_path:
        missing.append("PIPELINE_DB_PATH")
    if not log_file:
        missing.append("PIPELINE_LOG_FILE")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    db_host = env.get("PIPELINE_DB_HOST", "localhost")
    db_port_str = env.get("PIPELINE_DB_PORT", "5432")
    db_user = env.get("PIPELINE_DB_USER", "admin")
    db_pass = env.get("PIPELINE_DB_PASS", "")

    try:
        db_port = int(db_port_str)
    except ValueError as e:
        raise ValueError("PIPELINE_DB_PORT must be an integer") from e

    return Config(
        db_path=db_path,
        log_file=log_file,
        report_path=report_path,
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_pass=db_pass,
    )


def extract_log_lines(log_path: str) -> List[str]:
    """Read log lines from disk.

    Returns an empty list if the file does not exist.
    """

    if not os.path.exists(log_path):
        return []

    with open(log_path, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


def parse_log_line(line: str) -> Optional[Tuple[str, str, str]]:
    """Parse a raw log line into (timestamp_str, level, message).

    Returns None when the line doesn't match the expected base format.
    """

    m = _LOG_LINE_RE.match(line.strip())
    if not m:
        return None

    timestamp = f"{m.group('date')} {m.group('time')}"
    level = m.group("level")
    message = m.group("message")
    return timestamp, level, message


def transform_events(
    lines: Sequence[str],
) -> Tuple[List[LogError], List[ApiCall], List[UserEvent], Dict[str, str]]:
    """Transform raw log lines into typed events and derived session state.

    Returns:
        errors: parsed ERROR events
        api_calls: parsed API call events
        user_events: parsed user INFO events
        active_sessions: mapping of user_id -> login timestamp for users currently active
    """

    errors: List[LogError] = []
    api_calls: List[ApiCall] = []
    user_events: List[UserEvent] = []
    active_sessions: Dict[str, str] = {}

    for line in lines:
        parsed = parse_log_line(line)
        if not parsed:
            continue

        timestamp, level, message = parsed

        if level == "ERROR":
            errors.append(LogError(timestamp=timestamp, message=message))
            continue

        if level == "WARN":
            # WARN lines are not used for the report/DB, but are valid log lines.
            continue

        # INFO
        user_m = _USER_RE.match(message)
        if user_m:
            uid = user_m.group("uid")
            action = user_m.group("action").strip()
            if "logged in" in action:
                active_sessions[uid] = timestamp
            elif "logged out" in action:
                active_sessions.pop(uid, None)
            user_events.append(UserEvent(timestamp=timestamp, user_id=uid, action=action))
            continue

        api_m = _API_RE.match(message)
        if api_m:
            endpoint = api_m.group("endpoint")
            duration_ms = int(api_m.group("ms"))
            api_calls.append(ApiCall(timestamp=timestamp, endpoint=endpoint, duration_ms=duration_ms))
            continue

    return errors, api_calls, user_events, active_sessions


def summarize_errors(errors: Iterable[LogError]) -> Dict[str, int]:
    """Aggregate errors into a message -> count mapping."""

    counts: Dict[str, int] = {}
    for e in errors:
        counts[e.message] = counts.get(e.message, 0) + 1
    return counts


def summarize_api_latency(api_calls: Iterable[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""

    per_endpoint: Dict[str, List[int]] = {}
    for call in api_calls:
        per_endpoint.setdefault(call.endpoint, []).append(call.duration_ms)
    return per_endpoint


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if needed."""

    conn.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")


def load_metrics_to_db(
    db_path: str,
    error_counts: Mapping[str, int],
    api_latency_by_endpoint: Mapping[str, Sequence[int]],
    now: dt.datetime,
) -> None:
    """Load aggregated metrics into SQLite using parameterized queries."""

    with sqlite3.connect(db_path) as conn:
        ensure_schema(conn)

        now_str = str(now)
        for message, count in error_counts.items():
            conn.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now_str, message, int(count)),
            )

        for endpoint, times in api_latency_by_endpoint.items():
            if not times:
                continue
            avg_ms = sum(times) / len(times)
            conn.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now_str, endpoint, float(avg_ms)),
            )

        conn.commit()


def generate_report_html(
    error_counts: Mapping[str, int],
    api_latency_by_endpoint: Mapping[str, Sequence[int]],
    active_session_count: int,
) -> str:
    """Generate the HTML report content.

    The report includes the same information as the original script:
    - Error Summary (message + occurrences)
    - API Latency table (endpoint + avg)
    - Active Sessions count
    """

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"

    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, times in api_latency_by_endpoint.items():
        if not times:
            avg = 0.0
        else:
            avg = sum(times) / len(times)
        out += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_session_count} user(s) currently active</p>\n"

    out += "</body>\n</html>"
    return out


def write_report(report_path: str, html: str) -> None:
    """Write the report HTML to disk."""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)


def maybe_write_sample_log(log_path: str) -> None:
    """Create a sample log file if one does not exist.

    This keeps the original script's convenience behavior.
    """

    if os.path.exists(log_path):
        return

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def run_pipeline(config: Config) -> None:
    """Run the end-to-end pipeline."""

    maybe_write_sample_log(config.log_file)

    lines = extract_log_lines(config.log_file)
    errors, api_calls, _user_events, sessions = transform_events(lines)

    error_counts = summarize_errors(errors)
    api_latency_by_endpoint = summarize_api_latency(api_calls)

    print(
        f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}..."
    )

    now = dt.datetime.now()
    load_metrics_to_db(
        db_path=config.db_path,
        error_counts=error_counts,
        api_latency_by_endpoint=api_latency_by_endpoint,
        now=now,
    )

    html = generate_report_html(
        error_counts=error_counts,
        api_latency_by_endpoint=api_latency_by_endpoint,
        active_session_count=len(sessions),
    )
    write_report(config.report_path, html)

    print(f"Job finished at {now}")


def main() -> None:
    """Entry point."""

    config = load_config()
    run_pipeline(config)


if __name__ == "__main__":
    main()
