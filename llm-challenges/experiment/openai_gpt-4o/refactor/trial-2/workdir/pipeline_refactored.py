"""Log processing pipeline: extract, transform, and load server log data into a report."""

import datetime
import os
import re
import sqlite3
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_USER: str = os.getenv("DB_USER", "admin")
DB_PASS: str = os.getenv("DB_PASS", "changeme")


# ---------------------------------------------------------------------------
# Regex patterns for log parsing
# ---------------------------------------------------------------------------

# Matches any valid log line:  YYYY-MM-DD HH:MM:SS LEVEL rest-of-message
_LOG_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<msg>.+)$"
)

# Sub-patterns for structured INFO messages
_USER_PATTERN = re.compile(r"^User (\S+) (.+)$")
_API_PATTERN = re.compile(r"^API (\S+) took (\d+)ms$")


# Type aliases for readability
LogEntry = Dict[str, Any]
SessionMap = Dict[str, str]
ApiCall = Dict[str, Any]
ErrorSummary = Dict[str, int]
ApiStats = Dict[str, float]
ExtractResult = Tuple[List[LogEntry], SessionMap, List[ApiCall]]
TransformResult = Tuple[ErrorSummary, ApiStats]


# ---------------------------------------------------------------------------
# Extract: read and parse the log file
# ---------------------------------------------------------------------------

def extract_logs(filepath: str) -> ExtractResult:
    """Parse a server log file into structured event records.

    Returns three values:
    * entries — all parsed events (errors, user actions, warnings)
    * sessions — map of user ID to login timestamp
    * api_calls — API call records with endpoint and duration in ms

    Args:
        filepath: Path to the server log file.

    Returns:
        Tuple of (entries, sessions, api_calls).
    """
    entries: List[LogEntry] = []
    sessions: SessionMap = {}
    api_calls: List[ApiCall] = []

    if not os.path.exists(filepath):
        return entries, sessions, api_calls

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            m = _LOG_PATTERN.match(line)
            if not m:
                continue

            ts = m.group("ts")
            level = m.group("level")
            msg = m.group("msg")

            if level == "ERROR":
                entries.append({
                    "timestamp": ts,
                    "type": "ERR",
                    "message": msg,
                })

            elif level == "WARN":
                entries.append({
                    "timestamp": ts,
                    "type": "WARN",
                    "message": msg,
                })

            elif level == "INFO" and msg.startswith("User "):
                user_m = _USER_PATTERN.match(msg)
                if user_m:
                    uid = user_m.group(1)
                    action = user_m.group(2)
                    if "logged in" in action:
                        sessions[uid] = ts
                    elif "logged out" in action and uid in sessions:
                        del sessions[uid]
                    entries.append({
                        "timestamp": ts,
                        "type": "USR",
                        "user_id": uid,
                        "action": action,
                    })

            elif level == "INFO" and msg.startswith("API "):
                api_m = _API_PATTERN.match(msg)
                if api_m:
                    api_calls.append({
                        "timestamp": ts,
                        "endpoint": api_m.group(1),
                        "ms": int(api_m.group(2)),
                    })

    return entries, sessions, api_calls


# ---------------------------------------------------------------------------
# Transform: aggregate extracted data into summaries
# ---------------------------------------------------------------------------

def transform_data(
    entries: List[LogEntry],
    api_calls: List[ApiCall],
) -> TransformResult:
    """Aggregate raw log entries into error counts and API latency stats.

    Args:
        entries: Parsed event entries from extract_logs().
        api_calls: API call records from extract_logs().

    Returns:
        Tuple of (error_summary, api_stats).
        error_summary maps error messages to occurrence counts.
        api_stats maps endpoints to average latency in milliseconds.
    """
    error_summary: ErrorSummary = {}
    for e in entries:
        if e["type"] == "ERR":
            msg = e["message"]
            error_summary[msg] = error_summary.get(msg, 0) + 1

    endpoint_durations: Dict[str, List[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_durations.setdefault(ep, []).append(call["ms"])

    api_stats: ApiStats = {}
    for ep, durations in endpoint_durations.items():
        api_stats[ep] = sum(durations) / len(durations)

    return error_summary, api_stats


# ---------------------------------------------------------------------------
# Load: persist summaries to SQLite
# ---------------------------------------------------------------------------

def load_to_db(error_summary: ErrorSummary, api_stats: ApiStats) -> None:
    """Insert computed summaries into the SQLite database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        error_summary: Map of error message to occurrence count.
        api_stats: Map of API endpoint to average latency in ms.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat()

    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for ep, avg in api_stats.items():
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Report: generate the HTML output
# ---------------------------------------------------------------------------

def generate_report(
    error_summary: ErrorSummary,
    api_stats: ApiStats,
    active_sessions: int,
) -> None:
    """Write an HTML report with error summary, API latency table, and session count.

    Args:
        error_summary: Map of error message to occurrence count.
        api_stats: Map of API endpoint to average latency in ms.
        active_sessions: Number of currently active user sessions.
    """
    parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in error_summary.items():
        parts.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    parts.append("</ul>")

    parts.append("<h2>API Latency</h2>")
    parts.append("<table border='1'>")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in api_stats.items():
        parts.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    parts.append("</table>")

    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{active_sessions} user(s) currently active</p>")
    parts.append("</body>")
    parts.append("</html>")

    with open("report.html", "w") as f:
        f.write("\n".join(parts))


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full ETL pipeline."""
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    entries, sessions, api_calls = extract_logs(LOG_FILE)
    error_summary, api_stats = transform_data(entries, api_calls)
    load_to_db(error_summary, api_stats)
    generate_report(error_summary, api_stats, len(sessions))

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
    main()
