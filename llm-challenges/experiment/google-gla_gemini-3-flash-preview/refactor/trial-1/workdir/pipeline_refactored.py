"""Server log pipeline: extract, transform, and load metrics into a report.

Usage:
    python pipeline_refactored.py

Environment variables (all optional with sensible defaults):
    ZRB_DB_PATH       — path to SQLite database file (default: metrics.db)
    ZRB_LOG_FILE      — path to input server log (default: server.log)
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class LogError(Dict):
    """A logged ERROR line."""
    dt: str
    message: str


class LogUserAction(Dict):
    """An INFO line tracking a user login/logout."""
    dt: str
    user_id: str
    action: str


class LogApiCall(Dict):
    """An INFO line recording an API endpoint latency."""
    dt: str
    endpoint: str
    latency_ms: int


class LogWarning(Dict):
    """A WARN line."""
    dt: str
    message: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _env(key: str, default: str) -> str:
    """Read an environment variable, falling back to *default*."""
    return os.environ.get(key, default)


def load_config() -> dict:
    """Read all configuration from environment variables.

    Returns:
        A dict with keys ``db_path`` and ``log_file``.
    """
    return {
        "db_path": _env("ZRB_DB_PATH", "metrics.db"),
        "log_file": _env("ZRB_LOG_FILE", "server.log"),
    }


# ---------------------------------------------------------------------------
# Extract — parse the log file into structured records
# ---------------------------------------------------------------------------

# Compiled patterns — each captures the timestamp (group 1) and the payload.
_RE_ERROR = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.+)$"
)
_RE_USER = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\d+) (.+)$"
)
_RE_API = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (\S+) took (\d+)ms$"
)
_RE_WARN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.+)$"
)


def parse_logs(log_path: str) -> Tuple[
    List[LogError],
    List[LogApiCall],
    Dict[str, str],
]:
    """Parse *log_path* and return structured records.

    Returns:
        ``(errors, api_calls, active_sessions)`` where *active_sessions* is a
        ``{user_id: login_timestamp}`` map reflecting the **final** state of
        all login/logout lines seen.
    """
    errors: List[LogError] = []
    api_calls: List[LogApiCall] = []
    sessions: Dict[str, str] = {}

    if not os.path.exists(log_path):
        return errors, api_calls, sessions

    with open(log_path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            _parse_line(line, errors, api_calls, sessions)

    return errors, api_calls, sessions


def _parse_line(
    line: str,
    errors: List[LogError],
    api_calls: List[LogApiCall],
    sessions: Dict[str, str],
) -> None:
    """Route a single log *line* to the appropriate collector."""
    m = _RE_ERROR.match(line)
    if m:
        errors.append(LogError(dt=m.group(1), message=m.group(2)))
        return

    m = _RE_USER.match(line)
    if m:
        ts, uid, action = m.group(1), m.group(2), m.group(3)
        if "logged in" in action:
            sessions[uid] = ts
        elif "logged out" in action and uid in sessions:
            sessions.pop(uid, None)
        return

    m = _RE_API.match(line)
    if m:
        api_calls.append(LogApiCall(
            dt=m.group(1),
            endpoint=m.group(2),
            latency_ms=int(m.group(3)),
        ))
        return


# ---------------------------------------------------------------------------
# Transform — aggregate parsed records into summary data
# ---------------------------------------------------------------------------

def aggregate_errors(
    errors: List[LogError],
) -> Dict[str, int]:
    """Count occurrences of each distinct error message.

    Returns:
        ``{message: count}`` dict.
    """
    counts: Dict[str, int] = {}
    for err in errors:
        counts[err["message"]] = counts.get(err["message"], 0) + 1
    return counts


def compute_api_latency(
    api_calls: List[LogApiCall],
) -> Dict[str, float]:
    """Compute the average latency per endpoint.

    Returns:
        ``{endpoint: avg_latency_ms}`` dict.
    """
    buckets: Dict[str, List[int]] = {}
    for call in api_calls:
        buckets.setdefault(call["endpoint"], []).append(call["latency_ms"])

    averages: Dict[str, float] = {}
    for ep, times in buckets.items():
        averages[ep] = sum(times) / len(times)
    return averages


# ---------------------------------------------------------------------------
# Load — persist to database and produce the HTML report
# ---------------------------------------------------------------------------

def persist_metrics(
    db_path: str,
    error_counts: Dict[str, int],
    api_averages: Dict[str, float],
) -> None:
    """Write aggregated metrics into the SQLite database.

    Uses parameterised queries to eliminate SQL injection risk.
    Tables are created if they do not exist.
    """
    now = datetime.datetime.now().isoformat()

    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS errors "
            "(dt TEXT, message TEXT, count INTEGER)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics "
            "(dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        for msg, count in error_counts.items():
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count),
            )

        for ep, avg in api_averages.items():
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg),
            )

        conn.commit()
    finally:
        conn.close()


def generate_html_report(
    error_counts: Dict[str, int],
    api_averages: Dict[str, float],
    active_session_count: int,
) -> str:
    """Build an HTML report string from the aggregated data.

    Returns:
        A complete ``<html>`` document as a string.
    """
    parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in error_counts.items():
        parts.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    parts.extend(["</ul>", "<h2>API Latency</h2>", "<table border='1'>"])
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in api_averages.items():
        parts.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    parts.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full extract → transform → load pipeline."""
    config = load_config()

    # Extract
    errors, api_calls, sessions = parse_logs(config["log_file"])

    # Transform
    error_counts = aggregate_errors(errors)
    api_averages = compute_api_latency(api_calls)

    # Load — database
    persist_metrics(config["db_path"], error_counts, api_averages)

    # Load — report
    html = generate_html_report(
        error_counts=error_counts,
        api_averages=api_averages,
        active_session_count=len(sessions),
    )
    with open("report.html", "w") as f:
        f.write(html)

    print(f"Pipeline finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SEED_LOG_LINES = """\
2024-01-01 12:00:00 INFO User 42 logged in
2024-01-01 12:05:00 ERROR Database timeout
2024-01-01 12:05:05 ERROR Database timeout
2024-01-01 12:08:00 INFO API /users/profile took 250ms
2024-01-01 12:09:00 WARN Memory usage at 87%
2024-01-01 12:10:00 INFO User 42 logged out
"""


def _seed_log(log_path: str) -> None:
    """Write sample log data when *log_path* does not exist."""
    with open(log_path, "w") as f:
        f.write(_SEED_LOG_LINES)


def main() -> None:
    """CLI entry point — seed log if missing, then run the pipeline."""
    config = load_config()
    if not os.path.exists(config["log_file"]):
        _seed_log(config["log_file"])
    run_pipeline()


if __name__ == "__main__":
    main()
