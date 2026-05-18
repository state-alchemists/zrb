"""
Server log ETL pipeline.

Reads a structured server log, aggregates error counts and API latency metrics,
persists the results to SQLite, and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration (loaded from environment variables)
# ---------------------------------------------------------------------------

DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_USER: str = os.getenv("DB_USER", "admin")
DB_PASS: str = os.getenv("DB_PASS", "password123")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParsedLogLine:
    """Represents a single parsed log entry."""
    dt: str
    level: str
    message: str


@dataclass
class UserAction:
    """Represents a user login/logout action."""
    dt: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """Represents an API call with latency."""
    dt: str
    endpoint: str
    ms: int


@dataclass
class PipelineData:
    """Aggregated data produced during the Transform phase."""
    errors: Dict[str, int] = field(default_factory=dict)
    api_stats: Dict[str, List[int]] = field(default_factory=dict)
    sessions: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) (\w+) (.*)$"
)
_USER_ACTION_RE = re.compile(r"User (\S+) (.+)")
_API_CALL_RE = re.compile(r"API (\S+) took (\d+)ms")


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def extract_log_lines(log_path: str) -> List[str]:
    """Read raw log lines from *log_path*, skipping missing files gracefully.

    Args:
        log_path: Path to the server log file.

    Returns:
        A list of non-empty log lines.
    """
    if not os.path.exists(log_path):
        return []

    with open(log_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_log_line(line: str) -> Tuple[Optional[ParsedLogLine], Optional[UserAction], Optional[ApiCall]]:
    """Parse a single log line into its component parts.

    Supports ERROR, WARN, INFO (User/API), and any other level.

    Args:
        line: Raw log line.

    Returns:
        A 3-tuple of (parsed_log_line, user_action, api_call).  Unused slots
        are ``None``.
    """
    match = _LOG_LINE_RE.match(line)
    if not match:
        return None, None, None

    dt_str = f"{match.group(1)} {match.group(2)}"
    level = match.group(3)
    message = match.group(4)

    parsed = ParsedLogLine(dt=dt_str, level=level, message=message)
    user_action: Optional[UserAction] = None
    api_call: Optional[ApiCall] = None

    if level == "INFO":
        user_match = _USER_ACTION_RE.search(message)
        if user_match:
            user_action = UserAction(
                dt=dt_str,
                user_id=user_match.group(1),
                action=user_match.group(2),
            )

        api_match = _API_CALL_RE.search(message)
        if api_match:
            api_call = ApiCall(
                dt=dt_str,
                endpoint=api_match.group(1),
                ms=int(api_match.group(2)),
            )

    return parsed, user_action, api_call


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform_data(lines: List[str]) -> PipelineData:
    """Aggregate raw log lines into summary statistics.

    Args:
        lines: Raw log lines from the Extract phase.

    Returns:
        A ``PipelineData`` object containing error counts, API latency
        buckets, and active session state.
    """
    data = PipelineData()

    for line in lines:
        parsed, user_action, api_call = parse_log_line(line)
        if parsed is None:
            continue

        if parsed.level == "ERROR":
            data.errors[parsed.message] = data.errors.get(parsed.message, 0) + 1

        if user_action is not None:
            if "logged in" in user_action.action:
                data.sessions[user_action.user_id] = user_action.dt
            elif "logged out" in user_action.action and user_action.user_id in data.sessions:
                data.sessions.pop(user_action.user_id)

        if api_call is not None:
            data.api_stats.setdefault(api_call.endpoint, []).append(api_call.ms)

    return data


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_to_database(data: PipelineData, db_path: str) -> None:
    """Persist aggregated metrics to SQLite using parameterized queries.

    Args:
        data: Aggregated pipeline data.
        db_path: Path to the SQLite database file.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER} ...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now()

    for msg, count in data.errors.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, times in data.api_stats.items():
        avg_ms = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg_ms),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(data: PipelineData, output_path: str) -> None:
    """Write an HTML summary report to *output_path*.

    Args:
        data: Aggregated pipeline data.
        output_path: Destination path for the HTML report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in data.errors.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, times in data.api_stats.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(data.sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full ETL pipeline."""
    raw_lines = extract_log_lines(LOG_FILE)
    data = transform_data(raw_lines)
    load_to_database(data, DB_PATH)
    generate_report(data, "report.html")
    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()
