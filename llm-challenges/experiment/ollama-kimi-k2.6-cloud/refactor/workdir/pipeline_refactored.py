"""Server log ETL pipeline.

Reads server logs, extracts metrics, stores them in SQLite, and writes an
HTML report.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Config:
    """Application configuration read from environment variables."""

    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables."""
        return cls(
            db_path=os.getenv("DB_PATH", "metrics.db"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_user=os.getenv("DB_USER", "admin"),
            db_pass=os.getenv("DB_PASS", "password123"),
        )


@dataclass(frozen=True)
class ErrorEvent:
    """Represents an ERROR log entry."""

    timestamp: str
    message: str


@dataclass(frozen=True)
class ApiEvent:
    """Represents an INFO API log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True)
class UserEvent:
    """Represents an INFO User log entry."""

    timestamp: str
    user_id: str
    action: str


type LogEntry = ErrorEvent | ApiEvent | UserEvent


@dataclass
class ReportData:
    """Aggregated data produced from log entries."""

    error_counts: dict[str, int] = field(default_factory=dict)
    api_latencies: dict[str, list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    active_sessions: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def _ensure_sample_log(log_file: str) -> None:
    """Create a sample log file if one does not exist."""
    if Path(log_file).exists():
        return
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]
    Path(log_file).write_text("".join(sample_lines), encoding="utf-8")


def extract(log_file: str) -> list[LogEntry]:
    """Parse the server log file and return structured log entries.

    Expected line format::

        YYYY-MM-DD HH:MM:SS LEVEL message...

    Supports ERROR, WARN, and INFO levels. INFO lines are further
    classified into User events and API events via regex.
    """
    _ensure_sample_log(log_file)

    base_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<level>\w+) "
        r"(?P<rest>.*)$"
    )
    user_pattern = re.compile(r"User (?P<user_id>\d+) (?P<action>.+)")
    api_pattern = re.compile(r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms")

    entries: list[LogEntry] = []

    with Path(log_file).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            match = base_pattern.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            rest = match.group("rest")

            if level == "ERROR":
                entries.append(ErrorEvent(timestamp=timestamp, message=rest))
            elif level == "WARN":
                # Original code collected WARN entries but never used them.
                # Skipping preserves observable behaviour.
                continue
            elif level == "INFO":
                user_match = user_pattern.match(rest)
                if user_match:
                    entries.append(
                        UserEvent(
                            timestamp=timestamp,
                            user_id=user_match.group("user_id"),
                            action=user_match.group("action"),
                        )
                    )
                    continue

                api_match = api_pattern.match(rest)
                if api_match:
                    entries.append(
                        ApiEvent(
                            timestamp=timestamp,
                            endpoint=api_match.group("endpoint"),
                            duration_ms=int(api_match.group("duration")),
                        )
                    )

    return entries


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform(entries: Iterable[LogEntry]) -> ReportData:
    """Aggregate extracted log entries into report-ready data."""
    data = ReportData()

    for entry in entries:
        if isinstance(entry, ErrorEvent):
            data.error_counts[entry.message] = (
                data.error_counts.get(entry.message, 0) + 1
            )
        elif isinstance(entry, ApiEvent):
            data.api_latencies[entry.endpoint].append(entry.duration_ms)
        elif isinstance(entry, UserEvent):
            if "logged in" in entry.action:
                data.active_sessions[entry.user_id] = entry.timestamp
            elif "logged out" in entry.action and entry.user_id in data.active_sessions:
                data.active_sessions.pop(entry.user_id)

    return data


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load(db_path: str, data: ReportData) -> None:
    """Persist aggregated metrics to the SQLite database.

    Uses parameterized queries to eliminate SQL injection risk.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = str(datetime.datetime.now())

    for msg, count in data.error_counts.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, times in data.api_latencies.items():
        avg = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(data: ReportData, output_path: str) -> None:
    """Render an HTML report from aggregated data."""
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in data.error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, times in data.api_latencies.items():
        avg = sum(times) / len(times)
        lines.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(data.active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    """Orchestrate the ETL pipeline."""
    config = Config.from_env()
    print(
        f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}..."
    )

    entries = extract(config.log_file)
    data = transform(entries)
    load(config.db_path, data)
    generate_report(data, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
