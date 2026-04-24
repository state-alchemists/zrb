"""Log processing pipeline: Extract  Transform  Load.

This refactors the original `pipeline.py` into a safer, maintainable script:
- All configuration is read from environment variables
- SQL writes use parameterized queries (no string formatting)
- Log parsing is regex-based and more robust
- Logic is split into focused ETL functions

The generated `report.html` preserves the same information as the original:
- Error summary (message -> count)
- API latency table (endpoint -> average ms)
- Active session count
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# ----------------------------
# Configuration
# ----------------------------


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    report_path: Path

    # Kept for parity with the original script's notion of "credentials".
    # For sqlite these are unused, but they are still read from env to avoid
    # hardcoded secrets and to satisfy configuration requirements.
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


def _get_env(name: str, default: Optional[str] = None) -> str:
    """Read an environment variable.

    Args:
        name: Environment variable name.
        default: Default value if not set.

    Returns:
        The environment variable value.

    Raises:
        ValueError: If the variable is not set and no default is provided.
    """

    value = os.getenv(name, default)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    """Load configuration from environment variables.

    Required env vars:
        PIPELINE_DB_PATH
        PIPELINE_LOG_FILE

    Optional env vars:
        PIPELINE_REPORT_PATH (default: report.html)
        PIPELINE_DB_HOST (default: localhost)
        PIPELINE_DB_PORT (default: 5432)
        PIPELINE_DB_USER (default: admin)
        PIPELINE_DB_PASS (default: empty)

    Returns:
        Config object.
    """

    return Config(
        db_path=Path(_get_env("PIPELINE_DB_PATH")),
        log_file=Path(_get_env("PIPELINE_LOG_FILE")),
        report_path=Path(os.getenv("PIPELINE_REPORT_PATH", "report.html")),
        db_host=os.getenv("PIPELINE_DB_HOST", "localhost"),
        db_port=int(os.getenv("PIPELINE_DB_PORT", "5432")),
        db_user=os.getenv("PIPELINE_DB_USER", "admin"),
        db_pass=os.getenv("PIPELINE_DB_PASS", ""),
    )


# ----------------------------
# Extract: log parsing
# ----------------------------


@dataclass(frozen=True)
class LogRecord:
    """A single parsed log line."""

    timestamp: str
    level: str
    message: str


# Example: "2024-01-01 12:05:00 ERROR Database timeout"
_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<msg>.*)$"
)

# Example: "User 42 logged in"
_USER_ACTION_RE = re.compile(r"\bUser\s+(?P<uid>\S+)\s+(?P<action>.*)$")

# Example: "API /users/profile took 250ms"
_API_CALL_RE = re.compile(
    r"\bAPI\s+(?P<endpoint>\S+)(?:\s+.*?\btook\s+(?P<ms>\d+)ms\b)?"
)


def parse_log_line(line: str) -> Optional[LogRecord]:
    """Parse a log line with regex.

    Args:
        line: Raw line from the log file.

    Returns:
        LogRecord if the line matches the expected format, else None.
    """

    line = line.rstrip("\n")
    m = _LOG_LINE_RE.match(line)
    if not m:
        return None

    ts = f"{m.group('date')} {m.group('time')}"
    level = m.group("level")
    msg = m.group("msg").strip()
    return LogRecord(timestamp=ts, level=level, message=msg)


def read_log_records(log_path: Path) -> List[LogRecord]:
    """Extract phase: read and parse all log records."""

    if not log_path.exists():
        return []

    records: List[LogRecord] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            rec = parse_log_line(line)
            if rec is not None:
                records.append(rec)
    return records


# ----------------------------
# Transform: metrics computation
# ----------------------------


@dataclass(frozen=True)
class ApiCall:
    """A single API call observation."""

    timestamp: str
    endpoint: str
    ms: int


@dataclass(frozen=True)
class Metrics:
    """Computed metrics used both for DB load and report generation."""

    error_counts: Dict[str, int]
    api_latency_ms_by_endpoint: Dict[str, List[int]]
    active_sessions: Dict[str, str]


def extract_user_event(message: str) -> Optional[Tuple[str, str]]:
    """Extract (uid, action) from a user log message."""

    m = _USER_ACTION_RE.search(message)
    if not m:
        return None
    return m.group("uid"), m.group("action").strip()


def extract_api_call(message: str, timestamp: str) -> Optional[ApiCall]:
    """Extract an ApiCall from a log message."""

    m = _API_CALL_RE.search(message)
    if not m:
        return None

    endpoint = m.group("endpoint")
    ms_str = m.group("ms")
    ms = int(ms_str) if ms_str is not None else 0
    return ApiCall(timestamp=timestamp, endpoint=endpoint, ms=ms)


def compute_metrics(records: Sequence[LogRecord]) -> Metrics:
    """Transform phase: compute error summary, API latency stats, and sessions."""

    error_counts: Dict[str, int] = {}
    api_latency_ms_by_endpoint: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for rec in records:
        if rec.level == "ERROR":
            error_counts[rec.message] = error_counts.get(rec.message, 0) + 1
            continue

        if rec.level == "INFO":
            # User session tracking
            if "User" in rec.message:
                ue = extract_user_event(rec.message)
                if ue is not None:
                    uid, action = ue
                    if "logged in" in action:
                        active_sessions[uid] = rec.timestamp
                    elif "logged out" in action:
                        active_sessions.pop(uid, None)

            # API latency tracking
            if "API" in rec.message:
                call = extract_api_call(rec.message, rec.timestamp)
                if call is not None:
                    api_latency_ms_by_endpoint.setdefault(call.endpoint, []).append(call.ms)
            continue

        # WARN lines are ignored for metrics (kept in original d_list only)

    return Metrics(
        error_counts=error_counts,
        api_latency_ms_by_endpoint=api_latency_ms_by_endpoint,
        active_sessions=active_sessions,
    )


def average(values: Sequence[int]) -> float:
    """Compute average of a non-empty list of ints."""

    return float(sum(values)) / float(len(values))


# ----------------------------
# Load: sqlite persistence + report generation
# ----------------------------


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Create required tables if they do not exist."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def write_metrics_to_db(conn: sqlite3.Connection, metrics: Metrics, now: _dt.datetime) -> None:
    """Load phase: insert metrics using parameterized queries."""

    cur = conn.cursor()
    dt = str(now)

    for msg, count in metrics.error_counts.items():
        cur.execute("INSERT INTO errors VALUES (?, ?, ?)", (dt, msg, count))

    for ep, times in metrics.api_latency_ms_by_endpoint.items():
        avg_ms = average(times)
        cur.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (dt, ep, avg_ms))


def render_report_html(metrics: Metrics) -> str:
    """Render the HTML report with the same information as the original pipeline."""

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in metrics.error_counts.items():
        out += (
            "<li><b>" + err_msg + "</b>: " + str(count) + " occurrences</li>\n"
        )
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in metrics.api_latency_ms_by_endpoint.items():
        out += (
            "<tr><td>"
            + ep
            + "</td><td>"
            + str(round(average(times), 1))
            + "</td></tr>\n"
        )
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += "<p>" + str(len(metrics.active_sessions)) + " user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out


def write_report(report_path: Path, html: str) -> None:
    """Write report HTML to disk."""

    report_path.write_text(html, encoding="utf-8")


# ----------------------------
# Orchestration
# ----------------------------


def run_pipeline(cfg: Config) -> None:
    """Run the full ETL pipeline and write `report.html`.

    Extract: parse logs
    Transform: compute metrics
    Load: persist metrics + render report
    """

    print(f"Connecting to {cfg.db_host}:{cfg.db_port} as {cfg.db_user}...")

    records = read_log_records(cfg.log_file)
    metrics = compute_metrics(records)
    now = _dt.datetime.now()

    conn = sqlite3.connect(str(cfg.db_path))
    try:
        ensure_tables(conn)
        write_metrics_to_db(conn, metrics, now)
        conn.commit()
    finally:
        conn.close()

    html = render_report_html(metrics)
    write_report(cfg.report_path, html)

    print(f"Job finished at {now}")


def _maybe_create_sample_log(log_path: Path) -> None:
    """Create a sample log file if it doesn't exist (keeps original behavior)."""

    if log_path.exists():
        return

    log_path.write_text(
        """2024-01-01 12:00:00 INFO User 42 logged in
2024-01-01 12:05:00 ERROR Database timeout
2024-01-01 12:05:05 ERROR Database timeout
2024-01-01 12:08:00 INFO API /users/profile took 250ms
2024-01-01 12:09:00 WARN Memory usage at 87%
2024-01-01 12:10:00 INFO User 42 logged out
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    config = load_config()
    _maybe_create_sample_log(config.log_file)
    run_pipeline(config)
