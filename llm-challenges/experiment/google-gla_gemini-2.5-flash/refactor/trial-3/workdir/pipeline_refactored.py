"""
Server log processing pipeline — Extract, Transform, Load.

Reads a server.log, parses entries with regex, stores error summaries and
API metrics in SQLite, then generates report.html with:
- Error summary (message → occurrence count)
- API latency table (endpoint → average ms)
- Active session count
"""

import datetime
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------

# SQLite is local-file based, but these are surfaced for documentation/clarity.
_DEFAULT_DB_PATH = "metrics.db"
_DEFAULT_LOG_FILE = "server.log"


def load_config() -> Dict[str, str]:
    """Read configuration from environment variables with sensible defaults."""
    return {
        "db_path": os.environ.get("DB_PATH", _DEFAULT_DB_PATH),
        "log_file": os.environ.get("LOG_FILE", _DEFAULT_LOG_FILE),
        "db_host": os.environ.get("DB_HOST", "localhost"),
        "db_port": os.environ.get("DB_PORT", "5432"),
        "db_user": os.environ.get("DB_USER", "admin"),
        "db_pass": os.environ.get("DB_PASS", ""),
    }


# ---------------------------------------------------------------------------
# Extract phase
# ---------------------------------------------------------------------------

# Pattern: TIMESTAMP LEVEL MESSAGE
_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR|INFO|WARN) (.*)$"
)

# Sub-patterns for INFO message variants
_USER_RE = re.compile(r"^User (\S+) (.*)$")
_API_RE = re.compile(r"^API (\S+) took (\d+)ms$")


def parse_log_line(
    line: str,
) -> Optional[Dict[str, Any]]:
    """Parse a single log line into a structured dict, or None if malformed.

    Returns a dict with keys ``timestamp``, ``level``, and type-specific
    fields (``message`` for ERROR/WARN, ``user_id``/``action`` for user
    events, ``endpoint``/``duration_ms`` for API calls).
    """
    match = _LOG_LINE_RE.match(line)
    if not match:
        return None

    timestamp, level, message = match.groups()
    entry: Dict[str, Any] = {"timestamp": timestamp, "level": level}

    if level == "ERROR":
        entry["message"] = message.strip()

    elif level == "WARN":
        entry["message"] = message.strip()

    elif level == "INFO":
        user_match = _USER_RE.match(message)
        api_match = _API_RE.match(message)

        if user_match:
            entry["user_id"] = user_match.group(1)
            entry["action"] = user_match.group(2).strip()

        elif api_match:
            entry["endpoint"] = api_match.group(1)
            entry["duration_ms"] = int(api_match.group(2))

    return entry


def read_log_file(path: str) -> List[Dict[str, Any]]:
    """Read and parse every line in the log file.

    Returns a list of parsed entry dicts (malformed lines are skipped).
    """
    if not os.path.exists(path):
        return []

    entries: List[Dict[str, Any]] = []
    with open(path, "r") as f:
        for line in f:
            parsed = parse_log_line(line.rstrip("\n"))
            if parsed is not None:
                entries.append(parsed)
    return entries


# ---------------------------------------------------------------------------
# Transform phase
# ---------------------------------------------------------------------------


def separate_error_entries(
    entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter entries to only ERROR-level records."""
    return [e for e in entries if e["level"] == "ERROR"]


def separate_api_entries(
    entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter entries to only INFO-level API call records."""
    return [e for e in entries if e.get("endpoint") is not None]


def separate_user_entries(
    entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter entries to only INFO-level user-activity records."""
    return [e for e in entries if e.get("user_id") is not None]


def aggregate_error_counts(
    error_entries: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Tally occurrences of each unique error message.

    Returns {message_text: count}.
    """
    counts: Dict[str, int] = {}
    for entry in error_entries:
        msg = entry["message"]
        counts[msg] = counts.get(msg, 0) + 1
    return counts


def compute_api_latency(
    api_entries: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Compute average latency (ms) per API endpoint.

    Returns {endpoint: average_ms}.
    """
    raw: Dict[str, List[int]] = {}
    for entry in api_entries:
        ep = entry["endpoint"]
        raw.setdefault(ep, []).append(entry["duration_ms"])

    return {ep: sum(times) / len(times) for ep, times in raw.items()}


def count_active_sessions(
    user_entries: List[Dict[str, Any]],
) -> int:
    """Simulate session tracking: return number of currently active users.

    Tracks logins (+) and logouts (-) over time to produce a final count.
    """
    sessions: Dict[str, str] = {}
    for entry in user_entries:
        uid = entry["user_id"]
        action = entry["action"]
        if "logged in" in action:
            sessions[uid] = entry["timestamp"]
        elif "logged out" in action and uid in sessions:
            del sessions[uid]
    return len(sessions)


# ---------------------------------------------------------------------------
# Load phase — database
# ---------------------------------------------------------------------------


def init_database(db_path: str) -> sqlite3.Connection:
    """Create (if needed) and return a connection to the SQLite database.

    Ensures the ``errors`` and ``api_metrics`` tables exist.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()
    return conn


def insert_error_summary(
    conn: sqlite3.Connection, errors: Dict[str, int]
) -> None:
    """Write error counts into the ``errors`` table using parameterized queries."""
    now = datetime.datetime.now().isoformat()
    c = conn.cursor()
    # Parameterized — no string formatting of values
    c.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, count) for msg, count in errors.items()],
    )
    conn.commit()


def insert_api_metrics(
    conn: sqlite3.Connection, api_stats: Dict[str, float]
) -> None:
    """Write API latency averages into the ``api_metrics`` table."""
    now = datetime.datetime.now().isoformat()
    c = conn.cursor()
    c.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, ep, avg) for ep, avg in api_stats.items()],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Load phase — report
# ---------------------------------------------------------------------------


def escape_html(text: str) -> str:
    """Minimal HTML-entity escaping for safe embedding."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_report_html(
    error_counts: Dict[str, int],
    api_latency: Dict[str, float],
    active_session_count: int,
) -> str:
    """Build the full ``report.html`` document as a string."""
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in error_counts.items():
        lines.append(
            f"<li><b>{escape_html(msg)}</b>: {count} occurrences</li>"
        )
    lines.extend(["</ul>", "<h2>API Latency</h2>", "<table border='1'>"])
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in sorted(api_latency.items()):
        lines.append(
            f"<tr><td>{escape_html(ep)}</td>"
            f"<td>{avg:.1f}</td></tr>"
        )
    lines.extend(["</table>", "<h2>Active Sessions</h2>"])
    lines.append(f"<p>{active_session_count} user(s) currently active</p>")
    lines.extend(["</body>", "</html>"])
    return "\n".join(lines)


def write_report(html: str, path: str) -> None:
    """Write the HTML report to *path*."""
    with open(path, "w") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Convenience fixture (mirrors original __main__ behaviour)
# ---------------------------------------------------------------------------

_FIXTURE_LINES = [
    "2024-01-01 12:00:00 INFO User 42 logged in",
    "2024-01-01 12:05:00 ERROR Database timeout",
    "2024-01-01 12:05:05 ERROR Database timeout",
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
    "2024-01-01 12:09:00 WARN Memory usage at 87%",
    "2024-01-01 12:10:00 INFO User 42 logged out",
]


def _write_fixture(path: str) -> None:
    """Write sample log data if *path* does not exist."""
    if not os.path.exists(path):
        with open(path, "w") as f:
            for line in _FIXTURE_LINES:
                f.write(line + "\n")


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def run_pipeline(config: Optional[Dict[str, str]] = None) -> None:
    """Execute the full ETL pipeline: read log → transform → load DB + HTML.

    Expects an optional *config* dict (keys: ``db_path``, ``log_file``, etc.);
    falls back to :func:`load_config` when *config* is ``None``.
    """
    if config is None:
        config = load_config()

    db_path = config["db_path"]
    log_path = config["log_file"]

    # --- Extract ---
    entries = read_log_file(log_path)

    # --- Transform ---
    errors = aggregate_error_counts(separate_error_entries(entries))
    api_latency = compute_api_latency(separate_api_entries(entries))
    active_sessions = count_active_sessions(separate_user_entries(entries))

    # --- Load: database ---
    conn = init_database(db_path)
    insert_error_summary(conn, errors)
    insert_api_metrics(conn, api_latency)
    conn.close()

    # --- Load: report ---
    html = generate_report_html(errors, api_latency, active_sessions)
    write_report(html, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = load_config()
    _write_fixture(cfg["log_file"])
    run_pipeline(cfg)
