"""Server log pipeline: extract, transform, load, and report."""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def _getenv(key: str, default: str) -> str:
    """Return an environment variable or its default."""
    return os.getenv(key, default)


# ---------------------------------------------------------------------------
# Configuration (loaded from environment)
# ---------------------------------------------------------------------------
DB_PATH = _getenv("DB_PATH", "metrics.db")
LOG_FILE = _getenv("LOG_FILE", "server.log")
DB_HOST = _getenv("DB_HOST", "localhost")
DB_PORT = int(_getenv("DB_PORT", "5432"))
DB_USER = _getenv("DB_USER", "admin")
DB_PASS = _getenv("DB_PASS", "password123")


# ---------------------------------------------------------------------------
# Regex patterns for log parsing
# ---------------------------------------------------------------------------
_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<message>.*)$"
)

_USER_RE = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)"
)

_API_RE = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration_ms>\d+)ms"
)


def extract(log_path: str) -> List[dict]:
    """Parse the server log into a list of structured records.

    Args:
        log_path: Path to the log file to read.

    Returns:
        A list of record dictionaries, each containing timestamp, level,
        and parsed fields.
    """
    records: List[dict] = []
    path = Path(log_path)
    if not path.exists():
        return records

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            match = _LOG_LINE_RE.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            message = match.group("message")

            record: dict = {
                "timestamp": timestamp,
                "level": level,
            }

            if level == "ERROR":
                record["type"] = "ERR"
                record["message"] = message

            elif level == "INFO":
                user_match = _USER_RE.search(message)
                api_match = _API_RE.search(message)
                if user_match:
                    record["type"] = "USR"
                    record["user_id"] = user_match.group("user_id")
                    record["action"] = user_match.group("action")
                elif api_match:
                    record["type"] = "API"
                    record["endpoint"] = api_match.group("endpoint")
                    record["duration_ms"] = int(api_match.group("duration_ms"))
                else:
                    continue

            elif level == "WARN":
                record["type"] = "WARN"
                record["message"] = message

            else:
                continue

            records.append(record)

    return records


def transform(records: List[dict]) -> Tuple[Dict[str, int], Dict[str, List[int]], Dict[str, str]]:
    """Transform parsed records into aggregates.

    Args:
        records: Parsed log records from :func:`extract`.

    Returns:
        A 3-tuple of:
        - error_counts: mapping of error message -> occurrence count
        - api_stats: mapping of endpoint -> list of latencies in ms
        - active_sessions: mapping of user_id -> login timestamp
    """
    error_counts: Dict[str, int] = defaultdict(int)
    api_stats: Dict[str, List[int]] = defaultdict(list)
    active_sessions: Dict[str, str] = {}

    for rec in records:
        rec_type = rec.get("type")

        if rec_type == "ERR":
            msg = rec["message"]
            error_counts[msg] += 1

        elif rec_type == "USR":
            uid = rec["user_id"]
            action = rec["action"]
            if "logged in" in action:
                active_sessions[uid] = rec["timestamp"]
            elif "logged out" in action and uid in active_sessions:
                active_sessions.pop(uid)

        elif rec_type == "API":
            endpoint = rec["endpoint"]
            api_stats[endpoint].append(rec["duration_ms"])

    return dict(error_counts), dict(api_stats), active_sessions


def load(
    db_path: str,
    error_counts: Dict[str, int],
    api_stats: Dict[str, List[int]],
) -> None:
    """Persist aggregated metrics into SQLite using parameterized queries.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Mapping of error message -> count.
        api_stats: Mapping of endpoint -> list of latencies.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER} ...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
        """
    )

    now = str(datetime.datetime.now())

    for msg, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, times in api_stats.items():
        avg = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg),
        )

    conn.commit()
    conn.close()


def generate_report(
    error_counts: Dict[str, int],
    api_stats: Dict[str, List[int]],
    active_sessions: Dict[str, str],
) -> str:
    """Build an HTML report string.

    Args:
        error_counts: Mapping of error message -> count.
        api_stats: Mapping of endpoint -> list of latencies.
        active_sessions: Mapping of user_id -> login timestamp.

    Returns:
        The full HTML document as a string.
    """
    lines = [
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

    for ep, times in api_stats.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    return "\n".join(lines)


def bootstrap_sample_data(log_path: str) -> None:
    """Create a sample log file if none exists (for local testing)."""
    path = Path(log_path)
    if path.exists():
        return
    with path.open("w", encoding="utf-8") as fh:
        fh.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        fh.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        fh.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        fh.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        fh.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        fh.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def main() -> None:
    """Orchestrate the ETL pipeline and write report.html."""
    bootstrap_sample_data(LOG_FILE)

    records = extract(LOG_FILE)
    error_counts, api_stats, active_sessions = transform(records)
    load(DB_PATH, error_counts, api_stats)

    html = generate_report(error_counts, api_stats, active_sessions)
    with open("report.html", "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
