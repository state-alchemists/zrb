"""ETL pipeline for server logs.

This script:
- Extracts events from a server log file
- Transforms them into aggregates (error counts, average API latency, active sessions)
- Loads aggregates into SQLite
- Renders an HTML report with the same information as the legacy pipeline

Configuration is provided via environment variables (no hardcoded paths/credentials).

Environment variables:
- PIPELINE_DB_PATH: Path to the SQLite database file (default: metrics.db)
- PIPELINE_LOG_FILE: Path to the server log file (default: server.log)
- PIPELINE_REPORT_PATH: Output HTML report path (default: report.html)
- PIPELINE_DB_HOST / PIPELINE_DB_PORT / PIPELINE_DB_USER / PIPELINE_DB_PASS:
  Optional; used only for display/backward compatibility (SQLite ignores them).
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime configuration for the pipeline."""

    db_path: str
    log_file: str
    report_path: str

    # Kept for compatibility with the legacy script's connection banner.
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True)
class ApiCall:
    """Parsed API call event."""

    dt: str
    endpoint: str
    ms: int


_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|WARN|ERROR)\s+"
    r"(?P<message>.*)$"
)

_USER_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
_API_RE = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?\s*$")


def load_config(env: Mapping[str, str] = os.environ) -> PipelineConfig:
    """Load configuration from environment variables."""

    def _get_int(name: str, default: int) -> int:
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            return default
        return int(raw)

    return PipelineConfig(
        db_path=env.get("PIPELINE_DB_PATH", "metrics.db"),
        log_file=env.get("PIPELINE_LOG_FILE", "server.log"),
        report_path=env.get("PIPELINE_REPORT_PATH", "report.html"),
        db_host=env.get("PIPELINE_DB_HOST", "localhost"),
        db_port=_get_int("PIPELINE_DB_PORT", 5432),
        db_user=env.get("PIPELINE_DB_USER", "admin"),
        db_pass=env.get("PIPELINE_DB_PASS", ""),
    )


def iter_log_lines(log_file: str) -> Iterable[str]:
    """Yield log lines from the log file if it exists."""

    if not os.path.exists(log_file):
        return
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


def parse_log_line(line: str) -> Optional[Tuple[str, str, str]]:
    """Parse a raw log line.

    Returns:
        (dt, level, message) if the line matches the expected format, else None.
    """

    m = _LOG_LINE_RE.match(line)
    if not m:
        return None
    dt = f"{m.group('date')} {m.group('time')}"
    return dt, m.group("level"), m.group("message")


def extract_events(lines: Iterable[str]) -> Tuple[Dict[str, str], List[str], List[ApiCall]]:
    """Extract sessions, error messages, and API calls from log lines."""

    sessions: Dict[str, str] = {}
    error_messages: List[str] = []
    api_calls: List[ApiCall] = []

    for raw in lines:
        parsed = parse_log_line(raw)
        if not parsed:
            continue
        dt, level, message = parsed

        if level == "ERROR":
            error_messages.append(message.strip())
            continue

        if level == "WARN":
            # Not used in report, but legacy pipeline read it; we ignore for output.
            continue

        if level == "INFO":
            user_m = _USER_RE.match(message)
            if user_m:
                uid = user_m.group("uid")
                action = user_m.group("action").strip()
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action:
                    sessions.pop(uid, None)
                continue

            api_m = _API_RE.match(message)
            if api_m:
                endpoint = api_m.group("endpoint")
                ms_raw = api_m.group("ms")
                ms = int(ms_raw) if ms_raw is not None else 0
                api_calls.append(ApiCall(dt=dt, endpoint=endpoint, ms=ms))

    return sessions, error_messages, api_calls


def transform_error_summary(error_messages: Sequence[str]) -> Dict[str, int]:
    """Aggregate errors into a message -> count mapping."""

    counts: Dict[str, int] = {}
    for msg in error_messages:
        counts[msg] = counts.get(msg, 0) + 1
    return counts


def transform_api_latency(api_calls: Sequence[ApiCall]) -> Dict[str, float]:
    """Aggregate API calls into endpoint -> average milliseconds."""

    times_by_endpoint: Dict[str, List[int]] = {}
    for call in api_calls:
        times_by_endpoint.setdefault(call.endpoint, []).append(call.ms)

    avg_by_endpoint: Dict[str, float] = {}
    for endpoint, times in times_by_endpoint.items():
        avg_by_endpoint[endpoint] = sum(times) / len(times)
    return avg_by_endpoint


def init_db(conn: sqlite3.Connection) -> None:
    """Create required tables if they do not exist."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def load_metrics(
    conn: sqlite3.Connection,
    now: _dt.datetime,
    error_counts: Mapping[str, int],
    api_avg_ms: Mapping[str, float],
) -> None:
    """Persist aggregates to the database using parameterized queries."""

    cur = conn.cursor()

    # Parameterized inserts prevent SQL injection.
    cur.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now.isoformat(sep=" "), msg, count) for msg, count in error_counts.items()],
    )

    cur.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [
            (now.isoformat(sep=" "), endpoint, float(avg))
            for endpoint, avg in api_avg_ms.items()
        ],
    )


def render_report_html(
    error_counts: Mapping[str, int],
    api_avg_ms: Mapping[str, float],
    active_sessions_count: int,
) -> str:
    """Render the HTML report with the legacy sections and fields."""

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"

    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += (
            "<li><b>" + str(err_msg) + "</b>: " + str(count) + " occurrences</li>\n"
        )
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, avg in api_avg_ms.items():
        out += (
            "<tr><td>"
            + str(endpoint)
            + "</td><td>"
            + str(round(float(avg), 1))
            + "</td></tr>\n"
        )
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += (
        "<p>" + str(active_sessions_count) + " user(s) currently active</p>\n"
    )
    out += "</body>\n</html>"

    return out


def write_report(report_path: str, html: str) -> None:
    """Write the HTML report to disk."""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)


def ensure_sample_log_exists(log_file: str) -> None:
    """Create a sample log file matching the legacy script's demo behavior."""

    if os.path.exists(log_file):
        return
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def run_pipeline(config: PipelineConfig) -> None:
    """Run the Extract → Transform → Load pipeline and write the HTML report."""

    print(
        "Connecting to "
        + config.db_host
        + ":"
        + str(config.db_port)
        + " as "
        + config.db_user
        + "..."
    )

    sessions, error_messages, api_calls = extract_events(iter_log_lines(config.log_file))
    error_counts = transform_error_summary(error_messages)
    api_avg_ms = transform_api_latency(api_calls)

    now = _dt.datetime.now()
    conn = sqlite3.connect(config.db_path)
    try:
        init_db(conn)
        load_metrics(conn, now=now, error_counts=error_counts, api_avg_ms=api_avg_ms)
        conn.commit()
    finally:
        conn.close()

    html = render_report_html(
        error_counts=error_counts,
        api_avg_ms=api_avg_ms,
        active_sessions_count=len(sessions),
    )
    write_report(config.report_path, html)

    print("Job finished at " + str(_dt.datetime.now()))


def main() -> None:
    """CLI entry point."""

    config = load_config()
    ensure_sample_log_exists(config.log_file)
    run_pipeline(config)


if __name__ == "__main__":
    main()
