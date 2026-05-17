"""ETL pipeline for processing server logs into a SQLite DB and generating an HTML report.

This module reads a server log file, extracts key events (errors, API latency, user
session activity), loads aggregated metrics into a SQLite database, and writes an
HTML report (report.html) containing:

- Error summary (message -> count)
- API latency table (endpoint -> average ms)
- Active session count

Configuration is provided exclusively via environment variables.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file_path: Path
    output_report_path: Path

    # Credentials/connection-style variables are accepted for compatibility with the
    # legacy script, even though sqlite3 only uses a file path.
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass(frozen=True)
class ParsedLog:
    """Structured data extracted from the log file."""

    error_messages: List[str]
    api_calls: List[Tuple[str, int]]  # (endpoint, duration_ms)
    active_sessions: Dict[str, str]  # user_id -> last_login_dt (as string)


LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|WARN|ERROR)\s+"
    r"(?P<rest>.*)$"
)

USER_ACTION_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
API_CALL_RE = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+.*?took\s+(?P<ms>\d+)ms)?\s*$")


def load_config_from_env() -> Config:
    """Load configuration from environment variables.

    Required:
        PIPELINE_DB_PATH: path to SQLite database file
        PIPELINE_LOG_FILE: path to server log file

    Optional:
        PIPELINE_REPORT_PATH: output HTML path (default: report.html)
        PIPELINE_DB_HOST, PIPELINE_DB_PORT, PIPELINE_DB_USER, PIPELINE_DB_PASS

    Returns:
        Config object

    Raises:
        ValueError: if required environment variables are missing/invalid
    """

    def require(name: str) -> str:
        value = os.getenv(name)
        if value is None or value.strip() == "":
            raise ValueError(f"Missing required environment variable: {name}")
        return value

    db_path = Path(require("PIPELINE_DB_PATH"))
    log_file_path = Path(require("PIPELINE_LOG_FILE"))
    output_report_path = Path(os.getenv("PIPELINE_REPORT_PATH", "report.html"))

    db_host = os.getenv("PIPELINE_DB_HOST", "localhost")
    db_port_raw = os.getenv("PIPELINE_DB_PORT", "5432")
    try:
        db_port = int(db_port_raw)
    except ValueError as e:
        raise ValueError("PIPELINE_DB_PORT must be an integer") from e

    return Config(
        db_path=db_path,
        log_file_path=log_file_path,
        output_report_path=output_report_path,
        db_host=db_host,
        db_port=db_port,
        db_user=os.getenv("PIPELINE_DB_USER", ""),
        db_pass=os.getenv("PIPELINE_DB_PASS", ""),
    )


def parse_log_lines(lines: Iterable[str]) -> ParsedLog:
    """Extract error messages, API calls, and active sessions from log lines.

    The log format is expected to match lines like:
        2024-01-01 12:05:00 ERROR Database timeout
        2024-01-01 12:08:00 INFO API /users/profile took 250ms
        2024-01-01 12:00:00 INFO User 42 logged in

    Lines that don't match the expected format are ignored.
    """

    error_messages: List[str] = []
    api_calls: List[Tuple[str, int]] = []
    sessions: Dict[str, str] = {}

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        m = LOG_LINE_RE.match(line)
        if not m:
            continue

        timestamp = f"{m.group('date')} {m.group('time')}"
        level = m.group("level")
        rest = m.group("rest")

        if level == "ERROR":
            msg = rest.strip()
            if msg:
                error_messages.append(msg)
            continue

        if level == "INFO":
            um = USER_ACTION_RE.match(rest)
            if um:
                uid = um.group("uid")
                action = um.group("action").strip()
                if "logged in" in action:
                    sessions[uid] = timestamp
                elif "logged out" in action:
                    sessions.pop(uid, None)
                continue

            am = API_CALL_RE.match(rest)
            if am:
                endpoint = am.group("endpoint")
                ms_raw = am.group("ms")
                duration_ms = int(ms_raw) if ms_raw is not None else 0
                api_calls.append((endpoint, duration_ms))
            continue

        # WARN lines are not used in the final report, but keeping parsing behavior
        # aligned (ignore them) is intentional.

    return ParsedLog(error_messages=error_messages, api_calls=api_calls, active_sessions=sessions)


def read_log_file(path: Path) -> ParsedLog:
    """Read and parse a log file from disk."""

    if not path.exists():
        return ParsedLog(error_messages=[], api_calls=[], active_sessions={})

    with path.open("r", encoding="utf-8") as f:
        return parse_log_lines(f)


def aggregate_errors(error_messages: Iterable[str]) -> Dict[str, int]:
    """Aggregate error messages into a message -> count mapping."""

    counts: Dict[str, int] = {}
    for msg in error_messages:
        counts[msg] = counts.get(msg, 0) + 1
    return counts


def aggregate_api_latency(api_calls: Iterable[Tuple[str, int]]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""

    endpoint_stats: Dict[str, List[int]] = {}
    for endpoint, ms in api_calls:
        endpoint_stats.setdefault(endpoint, []).append(ms)
    return endpoint_stats


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create required tables if they don't exist."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")


def load_metrics_to_db(
    conn: sqlite3.Connection,
    error_counts: Dict[str, int],
    endpoint_stats: Dict[str, List[int]],
    now: Optional[dt.datetime] = None,
) -> None:
    """Load aggregated metrics into the database using parameterized queries."""

    current_time = (now or dt.datetime.now()).isoformat(sep=" ", timespec="seconds")
    cur = conn.cursor()

    for msg, count in error_counts.items():
        cur.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (current_time, msg, count),
        )

    for endpoint, times in endpoint_stats.items():
        avg_ms = sum(times) / len(times) if times else 0.0
        cur.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (current_time, endpoint, avg_ms),
        )

    conn.commit()


def render_report_html(
    error_counts: Dict[str, int],
    endpoint_stats: Dict[str, List[int]],
    active_sessions: Dict[str, str],
) -> str:
    """Render the HTML report with the same information as the legacy pipeline."""

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, times in endpoint_stats.items():
        avg = sum(times) / len(times) if times else 0.0
        out += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out


def write_report(path: Path, html: str) -> None:
    """Write the HTML report to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(html)


def run_pipeline(config: Config) -> None:
    """Run the full Extract → Transform → Load pipeline and write report.html."""

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    parsed = read_log_file(config.log_file_path)

    error_counts = aggregate_errors(parsed.error_messages)
    endpoint_stats = aggregate_api_latency(parsed.api_calls)

    conn = connect_sqlite(config.db_path)
    try:
        ensure_schema(conn)
        load_metrics_to_db(conn, error_counts, endpoint_stats)
    finally:
        conn.close()

    report_html = render_report_html(error_counts, endpoint_stats, parsed.active_sessions)
    write_report(config.output_report_path, report_html)

    print(f"Job finished at {dt.datetime.now().isoformat(sep=' ', timespec='seconds')}")


def _create_sample_log_if_missing(path: Path) -> None:
    """Create the sample log used by the legacy script when the file is missing."""

    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def main() -> None:
    """CLI entrypoint."""

    config = load_config_from_env()
    _create_sample_log_if_missing(config.log_file_path)
    run_pipeline(config)


if __name__ == "__main__":
    main()
