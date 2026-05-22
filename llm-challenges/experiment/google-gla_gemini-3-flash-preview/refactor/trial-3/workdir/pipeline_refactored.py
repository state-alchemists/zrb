
"""
Server log processing pipeline — Extract, Transform, Load (ETL).

Reads a structured server log file, parses events with regex, loads summaries
into a SQLite database with parameterized queries, and generates an HTML report.
Configurable entirely through environment variables.
"""

import datetime
import os
import re
import sqlite3
from typing import Any

# ---------------------------------------------------------------------------
# Configuration — all from environment variables with sensible defaults
# ---------------------------------------------------------------------------

METRICS_DB_PATH = os.environ.get("METRICS_DB_PATH", "metrics.db")
LOG_FILE_PATH = os.environ.get("LOG_FILE_PATH", "server.log")

# These are declared for environments where DB connectivity is required.
# The current pipeline only uses SQLite, so host/port/user/pass are printed
# for logging visibility but not consumed by any driver.
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123")

# ---------------------------------------------------------------------------
# Regex patterns for log line parsing
# ---------------------------------------------------------------------------

_LOG_LINE_RE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<body>.+)"
)

_USER_ACTION_RE = re.compile(
    r"^User\s+(?P<user_id>\d+)\s+(?P<action>.+)$"
)

_API_CALL_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+?)\s+took\s+(?P<duration>\d+)\s*ms$"
)


def parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a single log line into a structured event dict.

    Returns None for lines that don't match the expected format.

    Recognized event types:
        - ``error``    — an ERROR-level line
        - ``user``     — an INFO-level line describing a user action
        - ``api``      — an INFO-level line describing an API call
        - ``warning``  — a WARN-level line
    """
    m = _LOG_LINE_RE.match(line)
    if not m:
        return None

    event: dict[str, Any] = {
        "timestamp": m.group("timestamp"),
        "level": m.group("level"),
    }
    body = m.group("body")

    if event["level"] == "ERROR":
        event["type"] = "error"
        event["message"] = body

    elif event["level"] == "INFO":
        user_m = _USER_ACTION_RE.match(body)
        if user_m:
            event["type"] = "user"
            event["user_id"] = user_m.group("user_id")
            event["action"] = user_m.group("action")
        else:
            api_m = _API_CALL_RE.match(body)
            if api_m:
                event["type"] = "api"
                event["endpoint"] = api_m.group("endpoint")
                event["duration_ms"] = int(api_m.group("duration"))
            else:
                return None

    else:  # WARN
        event["type"] = "warning"
        event["message"] = body

    return event


def extract_log_data(log_path: str) -> tuple[list[dict], dict[str, str], list[dict]]:
    """Read *log_path*, parse every line, and track user sessions.

    Returns (events, active_sessions, api_calls).

    *active_sessions* maps user_id → login_timestamp for currently logged-in users.
    """
    events: list[dict] = []
    api_calls: list[dict] = []
    sessions: dict[str, str] = {}

    if not os.path.exists(log_path):
        return events, sessions, api_calls

    with open(log_path, "r") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            event = parse_log_line(line)
            if event is None:
                continue

            events.append(event)

            if event["type"] == "user":
                uid = event["user_id"]
                action = event["action"]
                if "logged in" in action:
                    sessions[uid] = event["timestamp"]
                elif "logged out" in action and uid in sessions:
                    del sessions[uid]

            elif event["type"] == "api":
                api_calls.append(event)

    return events, sessions, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def summarize_error_counts(events: list[dict]) -> dict[str, int]:
    """Aggregate error messages to occurrence counts."""
    counts: dict[str, int] = {}
    for ev in events:
        if ev["type"] == "error":
            msg = ev["message"]
            counts[msg] = counts.get(msg, 0) + 1
    return counts


def compute_avg_latency(api_calls: list[dict]) -> dict[str, float]:
    """Compute per-endpoint average latency in milliseconds."""
    durations: dict[str, list[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        durations.setdefault(ep, []).append(call["duration_ms"])

    return {ep: sum(times) / len(times) for ep, times in durations.items()}


# ---------------------------------------------------------------------------
# Load — database
# ---------------------------------------------------------------------------


def init_database(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and create tables if missing."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    return conn


def write_error_summary(
    conn: sqlite3.Connection,
    error_counts: dict[str, int],
    timestamp: str | None = None,
) -> None:
    """Insert error summary rows using a parameterized query (safe)."""
    if not error_counts:
        return
    ts = timestamp or datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    rows = [(ts, msg, count) for msg, count in error_counts.items()]
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)", rows
    )


def write_api_metrics(
    conn: sqlite3.Connection,
    avg_latency: dict[str, float],
    timestamp: str | None = None,
) -> None:
    """Insert API latency rows using a parameterized query (safe)."""
    if not avg_latency:
        return
    ts = timestamp or datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    rows = [(ts, ep, avg) for ep, avg in avg_latency.items()]
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)", rows
    )


# ---------------------------------------------------------------------------
# Load — HTML report
# ---------------------------------------------------------------------------


def _html_escape(text: str) -> str:
    """Minimal HTML escaping for safe inline rendering."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_html_report(
    error_counts: dict[str, int],
    avg_latency: dict[str, float],
    active_session_count: int,
) -> str:
    """Build the ``report.html`` content as a string."""
    parts: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in sorted(error_counts.items(), key=lambda x: -x[1]):
        parts.append(
            f"<li><b>{_html_escape(msg)}</b>: {count} occurrence(s)</li>"
        )
    parts.append("</ul>")

    parts.append("<h2>API Latency</h2>")
    parts.append("<table border='1'>")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep in sorted(avg_latency):
        avg = avg_latency[ep]
        parts.append(
            f"<tr><td>{_html_escape(ep)}</td><td>{avg:.1f}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{active_session_count} user(s) currently active</p>")
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def main() -> None:
    """Orchestrate the full ETL pipeline: extract, transform, load, report."""
    print(
        f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}..."
    )

    events, sessions, api_calls = extract_log_data(LOG_FILE_PATH)
    error_summary = summarize_error_counts(events)
    avg_latency = compute_avg_latency(api_calls)

    conn = init_database(METRICS_DB_PATH)
    try:
        write_error_summary(conn, error_summary)
        write_api_metrics(conn, avg_latency)
        conn.commit()
    finally:
        conn.close()

    report = generate_html_report(error_summary, avg_latency, len(sessions))
    with open("report.html", "w") as f:
        f.write(report)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Seed a sample log file if none exists (mirrors original behaviour)
    if not os.path.exists(LOG_FILE_PATH):
        seed_lines = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
            "2024-01-01 12:09:00 WARN Memory usage at 87%",
            "2024-01-01 12:10:00 INFO User 42 logged out",
        ]
        with open(LOG_FILE_PATH, "w") as f:
            for line in seed_lines:
                f.write(line + "\n")

    main()
