"""Pipeline to process server logs, extract metrics, and generate an HTML report.

Follows the Extract → Transform → Load pattern:
    Extract   — parse log lines into structured records
    Transform — aggregate errors, compute API latency, track sessions
    Load      — persist metrics to SQLite, write HTML report

All configuration is sourced from environment variables with local-dev defaults.
"""

import datetime
import os
import re
import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Configuration — override via environment variables for each environment
# ---------------------------------------------------------------------------

LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_PATH = os.environ.get("DB_PATH", "metrics.db")
REPORT_FILE = os.environ.get("REPORT_FILE", "report.html")

# Display-only values (SQLite does not use host/port/user)
_DB_HOST = os.environ.get("DB_HOST", "localhost")
_DB_PORT = int(os.environ.get("DB_PORT", "5432"))
_DB_USER = os.environ.get("DB_USER", "admin")

# ---------------------------------------------------------------------------
# Log-line regex patterns (one per supported message type)
# ---------------------------------------------------------------------------

_RE_ERROR = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.+)$"
)
_RE_USER = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User "
    r"(?P<user_id>\d+) (?P<action>.+)$"
)
_RE_API = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API "
    r"(?P<endpoint>\S+) took (?P<duration_ms>\d+)ms$"
)
_RE_WARN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.+)$"
)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


def parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a single log line with regex, returning structured data or *None*.

    Supported formats:
        <ts> ERROR <message>
        <ts> INFO User <id> <action>
        <ts> INFO API <endpoint> took <ms>ms
        <ts> WARN <message>

    Returns a dict with keys ``type``, ``timestamp``, and type-specific fields,
    or *None* if the line does not match any known pattern.
    """
    line = line.strip()
    if not line:
        return None

    patterns = [
        ("ERROR", _RE_ERROR),
        ("WARN", _RE_WARN),
        ("USER", _RE_USER),
        ("API", _RE_API),
    ]

    for log_type, pattern in patterns:
        match = pattern.match(line)
        if match is not None:
            result: dict[str, Any] = {
                "type": log_type,
                "timestamp": match.group("timestamp"),
            }
            # Copy remaining named groups
            for key in ("message", "user_id", "action", "endpoint", "duration_ms"):
                try:
                    value = match.group(key)
                except IndexError:
                    continue
                if value is not None:
                    result[key] = value
            # Cast numeric fields
            if "duration_ms" in result:
                result["duration_ms"] = int(result["duration_ms"])
            return result

    return None


def extract_logs(
    path: str,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    """Read and parse every line in the log file.

    Returns ``(error_events, sessions, api_calls)`` where:
        *error_events* — list of parsed ERROR events
        *sessions*     — ``{user_id: login_timestamp}`` for currently active users
        *api_calls*    — list of parsed API call events
    """
    errors: list[dict[str, Any]] = []
    sessions: dict[str, str] = {}
    api_calls: list[dict[str, Any]] = []

    if not os.path.exists(path):
        return errors, sessions, api_calls

    with open(path) as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed is None:
                continue

            kind = parsed["type"]

            if kind == "ERROR":
                errors.append(parsed)
            elif kind == "USER":
                user_id: str = parsed["user_id"]
                action: str = parsed["action"]
                if "logged in" in action:
                    sessions[user_id] = parsed["timestamp"]
                elif "logged out" in action and user_id in sessions:
                    del sessions[user_id]
            elif kind == "API":
                api_calls.append(parsed)
            # WARN events are parsed but not stored — same behaviour as the
            # original pipeline (WARN data was never used in the report).

    return errors, sessions, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def aggregate_errors(error_events: list[dict[str, Any]]) -> dict[str, int]:
    """Count occurrences of each unique error message.

    Returns ``{message: count}`` sorted by count descending.
    """
    counts: dict[str, int] = {}
    for event in error_events:
        msg: str = event["message"]
        counts[msg] = counts.get(msg, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def compute_api_latency(
    api_calls: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute the average duration (ms) per API endpoint.

    Returns ``{endpoint: avg_ms}``.
    """
    totals: dict[str, list[int]] = {}
    for call in api_calls:
        ep: str = call["endpoint"]
        totals.setdefault(ep, []).append(call["duration_ms"])

    return {ep: sum(times) / len(times) for ep, times in totals.items()}


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def init_db(path: str) -> sqlite3.Connection:
    """Open (or create) a SQLite database and ensure the target tables exist."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    return conn


def insert_errors(
    conn: sqlite3.Connection, errors: dict[str, int]
) -> None:
    """Insert aggregated error counts via a parameterized query.

    Each row receives the current timestamp, the error message, and its
    occurrence count.
    """
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, count) for msg, count in errors.items()],
    )


def insert_api_metrics(
    conn: sqlite3.Connection, api_latency: dict[str, float]
) -> None:
    """Insert API latency data via a parameterized query.

    Each row receives the current timestamp, the endpoint name, and the
    average duration in milliseconds.
    """
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, ep, avg) for ep, avg in api_latency.items()],
    )


def write_report(report_html: str, path: str) -> None:
    """Write the HTML report string to *path*."""
    with open(path, "w") as f:
        f.write(report_html)


def generate_report(
    errors: dict[str, int],
    api_latency: dict[str, float],
    active_count: int,
) -> str:
    """Build an HTML report string containing error summary, API latency table,
    and active session count.
    """
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in errors.items():
        lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    lines += ["</ul>", "<h2>API Latency</h2>", "<table border='1'>"]
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in api_latency.items():
        lines.append(f"<tr><td>{ep}</td><td>{avg:.1f}</td></tr>")
    lines += [
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_pipeline() -> None:
    """Run the full Extract → Transform → Load → Report pipeline."""
    print(
        f"Connecting to {_DB_HOST}:{_DB_PORT} as {_DB_USER}..."
    )

    # Extract
    error_events, sessions, api_calls = extract_logs(LOG_FILE)

    # Transform
    errors = aggregate_errors(error_events)
    api_latency = compute_api_latency(api_calls)

    # Load to DB
    conn = init_db(DB_PATH)
    try:
        insert_errors(conn, errors)
        insert_api_metrics(conn, api_latency)
        conn.commit()
    finally:
        conn.close()

    # Generate and write report
    report = generate_report(errors, api_latency, len(sessions))
    write_report(report, REPORT_FILE)

    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Seed a sample log file if none exists (dev convenience)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_pipeline()
