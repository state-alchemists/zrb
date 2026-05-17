"""
Server log processing pipeline.

Extracts events from server logs, computes metrics, stores them in a SQLite
database, and produces an HTML report.
"""

from __future__ import annotations

import os
import re
import sqlite3
import logging
from datetime import datetime
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Configuration — loaded from environment variables with safe defaults for
# local development. In production, set these explicitly.
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_USER: str = os.environ.get("DB_USER", "")
DB_PASS: str = os.environ.get("DB_PASS", "")
# DB_HOST and DB_PORT are noted for future use; the current implementation
# uses SQLite so they are not actively consumed.
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: str = os.environ.get("DB_PORT", "5432")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class LogEntry(NamedTuple):
    """A parsed log line."""
    timestamp: str
    level: str
    raw: str


class ErrorEntry(NamedTuple):
    """An aggregated error for insertion into the DB."""
    message: str
    count: int


class ApiMetricEntry(NamedTuple):
    """A computed API latency metric for insertion into the DB."""
    endpoint: str
    avg_ms: float


# ---------------------------------------------------------------------------
# ETL — Extract
# ---------------------------------------------------------------------------

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|WARN|INFO) "
    r"(?P<rest>.+)$"
)

USER_ACTION_PATTERN = re.compile(r"User (?P<uid>\S+) (?P<action>logged in|logged out)")
API_LATENCY_PATTERN = re.compile(r"API (?P<endpoint>\S+) took (?P<ms>\d+)ms")


def extract_log_entries(path: str) -> list[LogEntry]:
    """
    Read *path* and return a list of LogEntry objects for lines that match
    the expected log format. Missing or unparseable lines are silently skipped.
    """
    if not os.path.exists(path):
        logging.warning("Log file not found: %s", path)
        return []

    entries: list[LogEntry] = []
    with open(path, "r") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = LOG_PATTERN.match(line)
            if m:
                entries.append(LogEntry(
                    timestamp=m.group("timestamp"),
                    level=m.group("level"),
                    raw=m.group("rest"),
                ))
    return entries


# ---------------------------------------------------------------------------
# ETL — Transform
# ---------------------------------------------------------------------------

def transform_to_errors(entries: list[LogEntry]) -> tuple[dict[str, int], list[ErrorEntry]]:
    """
    Aggregate ERROR-level entries by message.

    Returns a dict suitable for HTML reporting and a list of ErrorEntry
    objects for database insertion.
    """
    counts: dict[str, int] = {}
    for e in entries:
        if e.level == "ERROR":
            counts[e.raw] = counts.get(e.raw, 0) + 1

    db_records = [ErrorEntry(message=msg, count=cnt) for msg, cnt in counts.items()]
    return counts, db_records


def transform_to_api_metrics(entries: list[LogEntry]) -> tuple[dict[str, list[int]], list[ApiMetricEntry]]:
    """
    Extract API latency data from INFO lines and compute per-endpoint averages.

    Returns a dict of endpoint -> list of latency values (for HTML) and a list
    of ApiMetricEntry objects (for DB insertion).
    """
    endpoint_times: dict[str, list[int]] = {}
    for e in entries:
        if e.level == "INFO":
            m = API_LATENCY_PATTERN.search(e.raw)
            if m:
                ep = m.group("endpoint")
                ms = int(m.group("ms"))
                endpoint_times.setdefault(ep, []).append(ms)

    db_records = [
        ApiMetricEntry(endpoint=ep, avg_ms=sum(times) / len(times))
        for ep, times in endpoint_times.items()
    ]
    return endpoint_times, db_records


def count_active_sessions(entries: list[LogEntry]) -> int:
    """
    Track user login/logout events and return the number of currently active
    sessions (logged in but not yet logged out).
    """
    active: set[str] = set()
    for e in entries:
        if e.level == "INFO":
            m = USER_ACTION_PATTERN.search(e.raw)
            if m:
                uid = m.group("uid")
                action = m.group("action")
                if action == "logged in":
                    active.add(uid)
                elif action == "logged out":
                    active.discard(uid)
    return len(active)


# ---------------------------------------------------------------------------
# ETL — Load
# ---------------------------------------------------------------------------

def init_database(path: str) -> sqlite3.Connection:
    """Create the metrics tables if they do not exist."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
    """)
    conn.commit()
    return conn


def load_errors(conn: sqlite3.Connection, records: list[ErrorEntry]) -> None:
    """Insert error aggregation records using a parameterized query."""
    now = datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, r.message, r.count) for r in records],
    )
    conn.commit()


def load_api_metrics(conn: sqlite3.Connection, records: list[ApiMetricEntry]) -> None:
    """Insert API latency records using a parameterized query."""
    now = datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, r.endpoint, r.avg_ms) for r in records],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_html_report(
    error_counts: dict[str, int],
    endpoint_times: dict[str, list[int]],
    active_sessions: int,
    output_path: str,
) -> None:
    """Write the HTML report to *output_path*."""
    rows = []
    for ep, times in sorted(endpoint_times.items()):
        avg = sum(times) / len(times)
        rows.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")

    error_items = "".join(
        f"<li><b>{msg}</b>: {cnt} occurrences</li>"
        for msg, cnt in sorted(error_counts.items())
    )

    html = (
        "<html>\n"
        "<head><title>System Report</title></head>\n"
        "<body>\n"
        "<h1>Error Summary</h1>\n"
        f"<ul>\n{error_items}\n</ul>\n"
        "<h2>API Latency</h2>\n"
        "<table border='1'>\n"
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
        + "".join(rows) +
        "</table>\n"
        "<h2>Active Sessions</h2>\n"
        f"<p>{active_sessions} user(s) currently active</p>\n"
        "</body>\n</html>"
    )

    with open(output_path, "w") as fh:
        fh.write(html)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full Extract → Transform → Load pipeline."""
    logging.info("Connecting to %s:%s as %s ...", DB_HOST, DB_PORT, DB_USER)

    # Extract
    entries = extract_log_entries(LOG_FILE)

    # Transform
    error_counts, error_records = transform_to_errors(entries)
    endpoint_times, api_records = transform_to_api_metrics(entries)
    active_sessions = count_active_sessions(entries)

    # Load
    conn = init_database(DB_PATH)
    load_errors(conn, error_records)
    load_api_metrics(conn, api_records)
    conn.close()

    # Report
    build_html_report(error_counts, endpoint_times, active_sessions, "report.html")

    logging.info("Job finished at %s", datetime.now())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Bootstrap a sample log file if none exists so the script is runnable
    # out of the box.
    if not os.path.exists(LOG_FILE):
        sample_lines = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
            "2024-01-01 12:09:00 WARN Memory usage at 87%",
            "2024-01-01 12:10:00 INFO User 42 logged out",
        ]
        with open(LOG_FILE, "w") as fh:
            fh.write("\n".join(sample_lines) + "\n")
        logging.info("Created sample %s", LOG_FILE)

    run_pipeline()