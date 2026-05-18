"""
Server log processing pipeline.

Extracts metrics from server logs, stores them in a SQLite database,
and generates an HTML report summarizing errors, API latency, and active sessions.
"""

import datetime
import os
import re
import sqlite3
from typing import Optional

# Configuration from environment variables
DB_PATH: Optional[str] = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: Optional[str] = os.environ.get("LOG_FILE", "server.log")
DB_HOST: Optional[str] = os.environ.get("DB_HOST", "localhost")
DB_PORT: Optional[int] = int(os.environ.get("DB_PORT", "5432"))
DB_USER: Optional[str] = os.environ.get("DB_USER", "admin")
DB_PASS: Optional[str] = os.environ.get("DB_PASS", "")


# ----------------------------------------------------------------------
# EXTRACT
# ----------------------------------------------------------------------

def extract_log_entries(log_path: str) -> tuple[list[dict], dict, list[dict]]:
    """
    Parse a server log file and extract structured entries.

    Args:
        log_path: Path to the server log file.

    Returns:
        A tuple containing:
        - events: List of event dicts (error, user, warning)
        - sessions: Dict mapping user_id -> login_datetime
        - api_calls: List of API call dicts with endpoint and duration
    """
    events: list[dict] = []
    sessions: dict[str, str] = {}
    api_calls: list[dict] = []

    # Compiled regex patterns for robust parsing
    # Format: 2024-01-01 12:00:00 LEVEL Message
    log_pattern = re.compile(
        r"^(?P<datetime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<level>ERROR|INFO|WARN) "
        r"(?P<message>.*)$"
    )

    # User action pattern: User <uid> <action>
    user_pattern = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")

    # API latency pattern: API /endpoint took Nms
    api_pattern = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")

    if not os.path.exists(log_path):
        return events, sessions, api_calls

    with open(log_path, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if not match:
                continue

            dt = match.group("datetime")
            level = match.group("level")
            message = match.group("message")

            if level == "ERROR":
                events.append({"dt": dt, "type": "ERR", "message": message})

            elif level == "INFO":
                user_match = user_pattern.match(message)
                if user_match:
                    uid = user_match.group("uid")
                    action = user_match.group("action")
                    if "logged in" in action:
                        sessions[uid] = dt
                    elif "logged out" in action and uid in sessions:
                        del sessions[uid]
                    events.append({"dt": dt, "type": "USR", "uid": uid, "action": action})

                api_match = api_pattern.match(message)
                if api_match:
                    endpoint = api_match.group("endpoint")
                    ms = int(api_match.group("ms"))
                    api_calls.append({"dt": dt, "endpoint": endpoint, "ms": ms})

            elif level == "WARN":
                events.append({"dt": dt, "type": "WARN", "message": message})

    return events, sessions, api_calls


# ----------------------------------------------------------------------
# TRANSFORM
# ----------------------------------------------------------------------

def transform_to_metrics(
    events: list[dict], api_calls: list[dict]
) -> tuple[dict[str, int], dict[str, float]]:
    """
    Aggregate raw log entries into summary metrics.

    Args:
        events: List of parsed event dicts.
        api_calls: List of API call dicts.

    Returns:
        A tuple containing:
        - error_counts: Dict mapping error message -> occurrence count
        - endpoint_latency: Dict mapping endpoint -> average latency in ms
    """
    # Count error occurrences by message
    error_counts: dict[str, int] = {}
    for event in events:
        if event["type"] == "ERR":
            msg = event["message"]
            error_counts[msg] = error_counts.get(msg, 0) + 1

    # Compute average latency per endpoint
    endpoint_latency: dict[str, list[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_latency.setdefault(ep, []).append(call["ms"])

    avg_latency: dict[str, float] = {
        ep: sum(times) / len(times)
        for ep, times in endpoint_latency.items()
    }

    return error_counts, avg_latency


# ----------------------------------------------------------------------
# LOAD
# ----------------------------------------------------------------------

def load_to_database(
    db_path: str,
    error_counts: dict[str, int],
    endpoint_latency: dict[str, float],
    db_host: str,
    db_port: int,
    db_user: str,
) -> None:
    """
    Persist aggregated metrics to a SQLite database using parameterized queries.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dict mapping error message -> count.
        endpoint_latency: Dict mapping endpoint -> average latency in ms.
        db_host: Database host (used only for logging).
        db_port: Database port (used only for logging).
        db_user: Database user (used only for logging).
    """
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables if they don't exist
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat()

    # Insert error counts using parameterized query
    for msg, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count)
        )

    # Insert API latency metrics using parameterized query
    for endpoint, avg_ms in endpoint_latency.items():
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg_ms)
        )

    conn.commit()
    conn.close()


# ----------------------------------------------------------------------
# REPORTING
# ----------------------------------------------------------------------

def generate_html_report(
    error_counts: dict[str, int],
    endpoint_latency: dict[str, float],
    active_session_count: int,
    output_path: str,
) -> None:
    """
    Generate an HTML report summarizing system metrics.

    Args:
        error_counts: Dict mapping error message -> count.
        endpoint_latency: Dict mapping endpoint -> average latency in ms.
        active_session_count: Number of currently active user sessions.
        output_path: Path where the HTML report should be written.
    """
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, avg_ms in sorted(endpoint_latency.items()):
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def run_pipeline() -> None:
    """
    Execute the full ETL pipeline: extract, transform, load, and report.
    """
    events, sessions, api_calls = extract_log_entries(LOG_FILE)

    error_counts, endpoint_latency = transform_to_metrics(events, api_calls)

    load_to_database(
        DB_PATH, error_counts, endpoint_latency,
        DB_HOST, DB_PORT, DB_USER
    )

    generate_html_report(
        error_counts, endpoint_latency,
        active_session_count=len(sessions),
        output_path="report.html"
    )

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()