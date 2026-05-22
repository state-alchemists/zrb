"""Pipeline for processing server logs and generating system reports.

Reads server logs via environment-variable configuration, extracts log entries
with regex parsing, transforms data into error summaries and API latency
statistics, and loads results into SQLite and an HTML report.
"""

import datetime
import os
import re
import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Read configuration from environment variables with sensible defaults.

    Returns:
        Dict with keys: db_path, log_file, db_host, db_port, db_user, db_pass.
    """
    return {
        "db_path": os.getenv("DB_PATH", "metrics.db"),
        "log_file": os.getenv("LOG_FILE", "server.log"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": int(os.getenv("DB_PORT", "5432")),
        "db_user": os.getenv("DB_USER", "admin"),
        "db_pass": os.getenv("DB_PASS", ""),
    }


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


def extract_log_entries(path: str) -> list[dict[str, Any]]:
    """Read and parse a server log file into structured entries.

    Each line is parsed with a regex that captures timestamp, level,
    and message. INFO lines are further inspected for User or API events.

    Args:
        path: Path to the log file.

    Returns:
        List of parsed log entry dicts.
    """
    line_pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(ERROR|INFO|WARN)\s+(.+)"
    )
    user_pattern = re.compile(r"User\s+(\S+)\s+(.+)")
    api_pattern = re.compile(r"API\s+(\S+)\s+took\s+(\d+)ms")

    if not os.path.exists(path):
        return []

    entries: list[dict[str, Any]] = []
    with open(path, "r") as f:
        for line in f:
            m = line_pattern.match(line.strip())
            if not m:
                continue

            timestamp, level, message = m.groups()
            entry: dict[str, Any] = {"dt": timestamp, "level": level}

            if level == "ERROR":
                entry["type"] = "error"
                entry["message"] = message
            elif level == "WARN":
                entry["type"] = "warn"
                entry["message"] = message
            elif level == "INFO":
                user_m = user_pattern.match(message)
                if user_m:
                    uid, action = user_m.groups()
                    entry["type"] = "user"
                    entry["user_id"] = uid
                    entry["action"] = action
                else:
                    api_m = api_pattern.match(message)
                    if api_m:
                        endpoint, duration = api_m.groups()
                        entry["type"] = "api"
                        entry["endpoint"] = endpoint
                        entry["duration_ms"] = int(duration)

            entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def transform_error_summary(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate error entries by message text.

    Args:
        entries: Parsed log entry dicts.

    Returns:
        Mapping of error message to occurrence count.
    """
    summary: dict[str, int] = {}
    for e in entries:
        if e.get("type") == "error":
            msg = e["message"]
            summary[msg] = summary.get(msg, 0) + 1
    return summary


def transform_api_latency(
    entries: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """Group API call durations by endpoint.

    Args:
        entries: Parsed log entry dicts.

    Returns:
        Mapping of endpoint to list of durations in ms.
    """
    stats: dict[str, list[int]] = {}
    for e in entries:
        if e.get("type") == "api":
            ep = e["endpoint"]
            stats.setdefault(ep, []).append(e["duration_ms"])
    return stats


def compute_active_sessions(entries: list[dict[str, Any]]) -> int:
    """Count currently active user sessions.

    Tracks login and logout events. A user who logged in but has not
    yet logged out is considered active.

    Args:
        entries: Parsed log entry dicts.

    Returns:
        Number of active sessions.
    """
    sessions: set[str] = set()
    for e in entries:
        if e.get("type") != "user":
            continue
        uid = e["user_id"]
        action = e["action"]
        if "logged in" in action:
            sessions.add(uid)
        elif "logged out" in action:
            sessions.discard(uid)
    return len(sessions)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_to_db(
    config: dict[str, Any],
    error_summary: dict[str, int],
    api_stats: dict[str, list[int]],
) -> None:
    """Persist aggregated data to SQLite using parameterized queries.

    Creates tables if they do not exist. Uses ``?`` placeholders to
    prevent SQL injection.

    Args:
        config: Application configuration dict.
        error_summary: Mapping of error message to count.
        api_stats: Mapping of endpoint to list of durations.
    """
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat()
    for msg, count in error_summary.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for ep, times in api_stats.items():
        avg = sum(times) / len(times) if times else 0.0
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg),
        )

    conn.commit()
    conn.close()


def load_report(
    error_summary: dict[str, int],
    api_stats: dict[str, list[int]],
    active_sessions: int,
    output_path: str,
) -> None:
    """Generate and write the HTML system report.

    Produces sections for error summary, API latency table, and active
    session count.

    Args:
        error_summary: Mapping of error message to count.
        api_stats: Mapping of endpoint to list of durations.
        active_sessions: Number of currently active sessions.
        output_path: Destination path for the HTML file.
    """
    html_parts = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err_msg, count in error_summary.items():
        html_parts.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    html_parts.append("</ul>")

    html_parts.append("<h2>API Latency</h2>")
    html_parts.append("<table border='1'>")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in api_stats.items():
        avg = sum(times) / len(times) if times else 0.0
        html_parts.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    html_parts.append("</table>")

    html_parts.append("<h2>Active Sessions</h2>")
    html_parts.append(f"<p>{active_sessions} user(s) currently active</p>")
    html_parts.append("</body>")
    html_parts.append("</html>")

    with open(output_path, "w") as f:
        f.write("\n".join(html_parts))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Orchestrate the ETL pipeline: extract, transform, load.

    Reads configuration from environment variables, parses the server log,
    aggregates metrics, and persists results to SQLite and an HTML report.
    """
    config = load_config()

    entries = extract_log_entries(config["log_file"])
    error_summary = transform_error_summary(entries)
    api_stats = transform_api_latency(entries)
    active_sessions = compute_active_sessions(entries)

    load_to_db(config, error_summary, api_stats)
    load_report(error_summary, api_stats, active_sessions, "report.html")


if __name__ == "__main__":
    main()
