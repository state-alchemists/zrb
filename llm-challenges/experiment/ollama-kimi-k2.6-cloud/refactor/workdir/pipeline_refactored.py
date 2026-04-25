"""Server log ETL pipeline with structured extraction, transform, and load."""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _getenv(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


DB_PATH = _getenv("DB_PATH", "metrics.db")
LOG_FILE = _getenv("LOG_FILE", "server.log")
DB_HOST = _getenv("DB_HOST", "localhost")
DB_PORT = int(_getenv("DB_PORT", "5432"))
DB_USER = _getenv("DB_USER", "admin")
DB_PASS = _getenv("DB_PASS", "password123")
REPORT_PATH = _getenv("REPORT_PATH", "report.html")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RawLogEvent:
    """A single parsed log line."""
    timestamp: str
    level: str
    payload: str


@dataclass
class SessionEvent:
    """User login / logout event."""
    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """API latency measurement."""
    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class TransformedData:
    """Aggregated data ready for load and report generation."""
    error_counts: dict[str, int] = field(default_factory=dict)
    endpoint_latencies: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    active_sessions: dict[str, str] = field(default_factory=dict)
    all_events: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<payload>.*)$"
)

USER_PATTERN = re.compile(r"^User (?P<user_id>\S+) (?P<action>.+)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<duration>\d+)ms$")


def extract_log_events(log_file_path: str) -> tuple[list[RawLogEvent], list[SessionEvent], list[ApiCall]]:
    """Parse *log_file_path* into raw events, session events, and API calls.

    Returns a three-tuple of (raw_events, session_events, api_calls).
    """
    raw_events: list[RawLogEvent] = []
    session_events: list[SessionEvent] = []
    api_calls: list[ApiCall] = []

    if not os.path.exists(log_file_path):
        return raw_events, session_events, api_calls

    with open(log_file_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue

            match = LOG_PATTERN.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            payload = match.group("payload")

            raw_events.append(RawLogEvent(timestamp, level, payload))

            if level == "INFO":
                user_match = USER_PATTERN.match(payload)
                if user_match:
                    session_events.append(SessionEvent(
                        timestamp=timestamp,
                        user_id=user_match.group("user_id"),
                        action=user_match.group("action"),
                    ))
                    continue

                api_match = API_PATTERN.match(payload)
                if api_match:
                    api_calls.append(ApiCall(
                        timestamp=timestamp,
                        endpoint=api_match.group("endpoint"),
                        duration_ms=int(api_match.group("duration")),
                    ))

    return raw_events, session_events, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform(
    raw_events: list[RawLogEvent],
    session_events: list[SessionEvent],
    api_calls: list[ApiCall],
) -> TransformedData:
    """Aggregate extracted events into counts, latencies, and active sessions."""
    data = TransformedData()
    data.endpoint_latencies = defaultdict(list)

    for event in raw_events:
        if event.level == "ERROR":
            data.error_counts[event.payload] = data.error_counts.get(event.payload, 0) + 1
            data.all_events.append({"d": event.timestamp, "t": "ERR", "m": event.payload})
        elif event.level == "WARN":
            data.all_events.append({"d": event.timestamp, "t": "WARN", "m": event.payload})

    for se in session_events:
        data.all_events.append({"d": se.timestamp, "t": "USR", "u": se.user_id, "a": se.action})
        if "logged in" in se.action:
            data.active_sessions[se.user_id] = se.timestamp
        elif "logged out" in se.action and se.user_id in data.active_sessions:
            data.active_sessions.pop(se.user_id)

    for call in api_calls:
        data.endpoint_latencies[call.endpoint].append(call.duration_ms)

    return data


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_metrics(db_path: str, data: TransformedData) -> None:
    """Persist aggregated metrics to *db_path* using parameterized queries."""
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER} ...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat(sep=" ", timespec="microseconds")

    for msg, count in data.error_counts.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for ep, times in data.endpoint_latencies.items():
        avg = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, ep, avg),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(data: TransformedData, output_path: str) -> None:
    """Write an HTML report summarising errors, API latency, and active sessions."""
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err_msg, count in data.error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for ep, times in data.endpoint_latencies.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{len(data.active_sessions)} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline(
    log_file_path: str = LOG_FILE,
    db_path: str = DB_PATH,
    report_path: str = REPORT_PATH,
) -> None:
    """Execute the full Extract → Transform → Load pipeline and generate the report."""
    raw_events, session_events, api_calls = extract_log_events(log_file_path)
    data = transform(raw_events, session_events, api_calls)
    load_metrics(db_path, data)
    generate_report(data, report_path)
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        sample_lines = [
            "2024-01-01 12:00:00 INFO User 42 logged in\n",
            "2024-01-01 12:05:00 ERROR Database timeout\n",
            "2024-01-01 12:05:05 ERROR Database timeout\n",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
            "2024-01-01 12:10:00 INFO User 42 logged out\n",
        ]
        with open(LOG_FILE, "w", encoding="utf-8") as fh:
            fh.writelines(sample_lines)
    run_pipeline()
