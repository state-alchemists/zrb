"""
pipeline_refactored.py — Extract, Transform, Load pipeline for server log analysis.

Produces report.html with error summary, API latency table, and active session count.
All configuration comes from environment variables.
"""

import datetime
import html
import os
import re
import sqlite3
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("METRICS_DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("METRICS_LOG_FILE", "server.log")


# ---------------------------------------------------------------------------
# Extract — read log lines from file
# ---------------------------------------------------------------------------

def read_log_lines(path: str) -> List[str]:
    """Read all non-empty lines from *path*.

    Args:
        path: Path to the log file.

    Returns:
        A list of stripped log lines.
    """
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Transform — regex-based log-line parsing into structured records
# ---------------------------------------------------------------------------

# Each pattern captures: timestamp, level, and the domain-specific payload.
# Named groups make the intent clear and the values easy to extract.

_RE_ERROR = re.compile(
    r"^(?P<timestamp>\S+ \S+) ERROR (?P<message>.+)$"
)
_RE_USER = re.compile(
    r"^(?P<timestamp>\S+ \S+) INFO User (?P<user_id>\S+) (?P<action>.+)$"
)
_RE_API = re.compile(
    r"^(?P<timestamp>\S+ \S+) INFO API (?P<endpoint>\S+) took (?P<duration_ms>\d+)ms$"
)
_RE_WARN = re.compile(
    r"^(?P<timestamp>\S+ \S+) WARN (?P<message>.+)$"
)

# Named tuple-like aliases for readability
ErrorRecord = Dict[str, str]
UserRecord = Dict[str, str]
ApiRecord = Dict[str, str]


def parse_error(match: re.Match) -> ErrorRecord:
    """Build an error record from a regex match on an ERROR line."""
    return {
        "dt": match.group("timestamp"),
        "message": match.group("message"),
    }


def parse_user_event(match: re.Match) -> Tuple[UserRecord, str, str]:
    """Build a user-event record from a regex match on an INFO User line.

    Returns:
        (record, user_id, action_string)
    """
    uid = match.group("user_id")
    action = match.group("action")
    record: UserRecord = {
        "dt": match.group("timestamp"),
        "user_id": uid,
        "action": action,
    }
    return record, uid, action


def parse_api_call(match: re.Match) -> ApiRecord:
    """Build an API-call record from a regex match on an INFO API line."""
    return {
        "dt": match.group("timestamp"),
        "endpoint": match.group("endpoint"),
        "duration_ms": int(match.group("duration_ms")),
    }


def parse_warning(match: re.Match) -> Dict[str, str]:
    """Build a warning record from a regex match on a WARN line."""
    return {
        "dt": match.group("timestamp"),
        "message": match.group("message"),
    }


def transform_logs(
    lines: List[str],
) -> Tuple[
    List[ErrorRecord],
    List[UserRecord],
    List[ApiRecord],
    List[Dict[str, str]],
]:
    """Parse all log lines into structured record lists.

    Args:
        lines: Raw log lines from the log file.

    Returns:
        (errors, user_events, api_calls, warnings) — four parsed lists.
    """
    errors: List[ErrorRecord] = []
    user_events: List[UserRecord] = []
    api_calls: List[ApiRecord] = []
    warnings: List[Dict[str, str]] = []

    for line in lines:
        if m := _RE_ERROR.match(line):
            errors.append(parse_error(m))
        elif m := _RE_USER.match(line):
            record, _uid, _action = parse_user_event(m)
            user_events.append(record)
        elif m := _RE_API.match(line):
            api_calls.append(parse_api_call(m))
        elif m := _RE_WARN.match(line):
            warnings.append(parse_warning(m))

    return errors, user_events, api_calls, warnings


# ---------------------------------------------------------------------------
# Transform — aggregate records into summary data for loading
# ---------------------------------------------------------------------------

def aggregate_error_summary(
    errors: List[ErrorRecord],
) -> Dict[str, int]:
    """Count occurrences of each distinct error message.

    Args:
        errors: Parsed error records.

    Returns:
        {message: count} sorted by count descending.
    """
    summary: Dict[str, int] = {}
    for rec in errors:
        msg = rec["message"]
        summary[msg] = summary.get(msg, 0) + 1
    # Return in descending-count order
    return dict(sorted(summary.items(), key=lambda kv: -kv[1]))


def aggregate_api_latency(
    api_calls: List[ApiRecord],
) -> Dict[str, float]:
    """Compute average latency per API endpoint.

    Args:
        api_calls: Parsed API-call records.

    Returns:
        {endpoint: average_ms} sorted by endpoint name.
    """
    totals: Dict[str, List[int]] = {}
    for rec in api_calls:
        totals.setdefault(rec["endpoint"], []).append(rec["duration_ms"])

    averages: Dict[str, float] = {}
    for ep, durations in totals.items():
        averages[ep] = sum(durations) / len(durations)

    return dict(sorted(averages.items()))


def track_sessions(
    user_events: List[UserRecord],
) -> Dict[str, str]:
    """Track login/logout events to determine active sessions.

    Args:
        user_events: Parsed user-event records (logged in / logged out).

    Returns:
        {user_id: login_timestamp} for currently active sessions.
    """
    sessions: Dict[str, str] = {}
    for rec in user_events:
        uid = rec["user_id"]
        action = rec["action"]
        if "logged in" in action:
            sessions[uid] = rec["dt"]
        elif "logged out" in action and uid in sessions:
            del sessions[uid]
    return sessions


# ---------------------------------------------------------------------------
# Load — persist aggregated data to SQLite
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    """Open a connection to *db_path* and ensure tables exist.

    Args:
        db_path: Filesystem path to the SQLite database.

    Returns:
        An open connection (caller must close).
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()
    return conn


def write_error_summary(
    conn: sqlite3.Connection,
    error_summary: Dict[str, int],
) -> None:
    """Insert error summary rows with parameterized queries.

    Args:
        conn: Open SQLite connection.
        error_summary: {message: count} from aggregation.
    """
    now = datetime.datetime.now().isoformat()
    for msg, count in error_summary.items():
        conn.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )
    conn.commit()


def write_api_metrics(
    conn: sqlite3.Connection,
    api_averages: Dict[str, float],
) -> None:
    """Insert API latency rows with parameterized queries.

    Args:
        conn: Open SQLite connection.
        api_averages: {endpoint: avg_ms} from aggregation.
    """
    now = datetime.datetime.now().isoformat()
    for endpoint, avg in api_averages.items():
        conn.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Load — generate report.html
# ---------------------------------------------------------------------------

def _render_error_list(error_summary: Dict[str, int]) -> str:
    """Render the error summary section as HTML."""
    parts: List[str] = ['<h1>Error Summary</h1>\n<ul>']
    for msg, count in error_summary.items():
        safe_msg = html.escape(msg)
        parts.append(f"<li><b>{safe_msg}</b>: {count} occurrences</li>")
    parts.append("</ul>")
    return "\n".join(parts)


def _render_api_table(api_averages: Dict[str, float]) -> str:
    """Render the API latency table as HTML."""
    parts: List[str] = [
        '<h2>API Latency</h2>\n<table border="1">',
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ]
    for ep, avg in api_averages.items():
        safe_ep = html.escape(ep)
        parts.append(f"<tr><td>{safe_ep}</td><td>{avg:.1f}</td></tr>")
    parts.append("</table>")
    return "\n".join(parts)


def _render_session_count(sessions: Dict[str, str]) -> str:
    """Render the active-session count as HTML."""
    count = len(sessions)
    return f"<h2>Active Sessions</h2>\n<p>{count} user(s) currently active</p>"


def generate_report(
    error_summary: Dict[str, int],
    api_averages: Dict[str, float],
    sessions: Dict[str, str],
    output_path: str = "report.html",
) -> None:
    """Write an HTML report to *output_path*.

    Args:
        error_summary: {message: count} sorted by descending count.
        api_averages: {endpoint: avg_ms} sorted by endpoint name.
        sessions: {user_id: login_timestamp} for active sessions.
        output_path: Destination path for the HTML file.
    """
    sections = [
        "<!DOCTYPE html>",
        '<html><head><title>System Report</title></head><body>',
        _render_error_list(error_summary),
        _render_api_table(api_averages),
        _render_session_count(sessions),
        "</body></html>",
    ]
    html_content = "\n".join(sections)
    with open(output_path, "w") as f:
        f.write(html_content)


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(log_path: str, db_path: str, report_path: str) -> None:
    """Run the full ETL pipeline: read logs, transform, load to DB + report.

    Args:
        log_path: Path to the server log file.
        db_path: Path to the SQLite database file.
        report_path: Path for the generated HTML report.
    """
    # --- Extract ---
    lines = read_log_lines(log_path)
    print(f"Read {len(lines)} log lines from {log_path}")

    # --- Transform ---
    errors, user_events, api_calls, _warnings = transform_logs(lines)
    error_summary = aggregate_error_summary(errors)
    api_averages = aggregate_api_latency(api_calls)
    sessions = track_sessions(user_events)

    print(f"  Errors:    {len(errors)} lines → {len(error_summary)} distinct messages")
    print(f"  API calls: {len(api_calls)} calls across {len(api_averages)} endpoints")
    print(f"  Sessions:  {len(sessions)} active user(s)")

    # --- Load (DB) ---
    conn = init_db(db_path)
    try:
        write_error_summary(conn, error_summary)
        write_api_metrics(conn, api_averages)
    finally:
        conn.close()

    # --- Load (report) ---
    generate_report(error_summary, api_averages, sessions, report_path)
    print(f"Report written to {report_path}")


def _seed_sample_log(log_path: str) -> None:
    """Write sample log data when the log file does not exist.

    Args:
        log_path: Path where the sample log should be written.
    """
    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(log_path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        _seed_sample_log(LOG_FILE)
    run_pipeline(LOG_FILE, DB_PATH, "report.html")
