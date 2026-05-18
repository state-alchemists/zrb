"""Refactored log processing pipeline.

This module implements an Extract → Transform → Load (ETL) workflow for
processing application server logs, persisting aggregate metrics to a SQLite
store, and generating an HTML report.

Configuration is provided exclusively via environment variables:

- LOG_FILE: path to the server log file (default: "server.log")
- DB_PATH: path to the SQLite database file (default: "metrics.db")
- DB_HOST: database host (for display/logging only, default: "localhost")
- DB_PORT: database port (for display/logging only, default: "5432")
- DB_USER: database user (for display/logging only, default: "admin")
- DB_PASS: database password (unused by sqlite, display only, default: "password123")

The generated report is written to "report.html" in the working directory and
contains the same information as the original implementation:

- Error summary (distinct error message with occurrence count)
- API latency table (endpoint and average latency in ms)
- Active session count (number of currently active user sessions)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import os
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables.

    All attributes have sensible defaults to preserve the original behaviour
    when environment variables are not explicitly set.
    """

    log_file: Path
    db_path: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


def load_config() -> Config:
    """Load configuration from environment variables.

    Returns
    -------
    Config
        A configuration object populated from environment variables, falling
        back to the original hardcoded values when unset.
    """

    log_file = Path(os.environ.get("LOG_FILE", "server.log"))
    db_path = Path(os.environ.get("DB_PATH", "metrics.db"))
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port_raw = os.environ.get("DB_PORT", "5432")
    db_user = os.environ.get("DB_USER", "admin")
    db_pass = os.environ.get("DB_PASS", "password123")

    try:
        db_port = int(db_port_raw)
    except ValueError:
        db_port = 5432

    return Config(
        log_file=log_file,
        db_path=db_path,
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_pass=db_pass,
    )


# ---------------------------------------------------------------------------
# Data models and parsing (Extract)
# ---------------------------------------------------------------------------


@dataclass
class ErrorLog:
    timestamp: dt.datetime
    message: str


@dataclass
class UserEvent:
    timestamp: dt.datetime
    user_id: str
    action: str


@dataclass
class ApiCall:
    timestamp: dt.datetime
    endpoint: str
    duration_ms: int


LOG_LINE_REGEX = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"  # date
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"     # time
    r"(?P<level>INFO|ERROR|WARN)\s+"        # log level
    r"(?P<rest>.+)$"                         # remainder of the line
)

USER_EVENT_REGEX = re.compile(r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)")
API_CALL_REGEX = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+.*?took\s+(?P<duration>\d+)ms",
    re.IGNORECASE,
)


def parse_timestamp(date_str: str, time_str: str) -> dt.datetime:
    """Parse separate date and time strings into a ``datetime`` instance."""

    return dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")


@dataclasses.dataclass
class ParsedLogs:
    """Container for all parsed log artefacts from the extract phase."""

    errors: List[ErrorLog]
    user_events: List[UserEvent]
    api_calls: List[ApiCall]


def extract_logs(log_path: Path) -> ParsedLogs:
    """Extract structured records from a log file.

    Parameters
    ----------
    log_path:
        Path to the server log file.

    Returns
    -------
    ParsedLogs
        Parsed error logs, user events and API calls.
    """

    errors: List[ErrorLog] = []
    user_events: List[UserEvent] = []
    api_calls: List[ApiCall] = []

    if not log_path.exists():
        return ParsedLogs(errors=errors, user_events=user_events, api_calls=api_calls)

    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = LOG_LINE_REGEX.match(line)
            if not match:
                # Skip malformed lines instead of failing the whole pipeline.
                continue

            ts = parse_timestamp(match.group("date"), match.group("time"))
            level = match.group("level")
            rest = match.group("rest")

            if level == "ERROR":
                errors.append(ErrorLog(timestamp=ts, message=rest))

            elif level == "WARN":
                # Warnings are currently only used in the HTML report in
                # aggregate form; preserve message content via ErrorLog type.
                # This mirrors original behaviour of storing them in ``d_list``.
                errors.append(ErrorLog(timestamp=ts, message=rest))

            elif level == "INFO":
                user_match = USER_EVENT_REGEX.search(rest)
                api_match = API_CALL_REGEX.search(rest)

                if user_match:
                    user_events.append(
                        UserEvent(
                            timestamp=ts,
                            user_id=user_match.group("user_id"),
                            action=user_match.group("action"),
                        )
                    )

                if api_match:
                    api_calls.append(
                        ApiCall(
                            timestamp=ts,
                            endpoint=api_match.group("endpoint"),
                            duration_ms=int(api_match.group("duration")),
                        )
                    )

    return ParsedLogs(errors=errors, user_events=user_events, api_calls=api_calls)


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def aggregate_errors(errors: Iterable[ErrorLog]) -> Mapping[str, int]:
    """Aggregate error messages and return a count per distinct message."""

    messages = [err.message for err in errors if err.message]
    return Counter(messages)


def compute_active_sessions(user_events: Iterable[UserEvent]) -> int:
    """Compute number of currently active sessions.

    A session is considered active if a user has a "logged in" event without
    a corresponding subsequent "logged out" event.
    """

    active_sessions: Dict[str, dt.datetime] = {}

    for event in sorted(user_events, key=lambda e: e.timestamp):
        if "logged in" in event.action:
            active_sessions[event.user_id] = event.timestamp
        elif "logged out" in event.action and event.user_id in active_sessions:
            active_sessions.pop(event.user_id)

    return len(active_sessions)


def aggregate_api_latency(api_calls: Iterable[ApiCall]) -> Mapping[str, float]:
    """Compute average latency per API endpoint in milliseconds."""

    durations: DefaultDict[str, List[int]] = defaultdict(list)
    for call in api_calls:
        durations[call.endpoint].append(call.duration_ms)

    return {ep: (sum(vals) / len(vals)) for ep, vals in durations.items() if vals}


# ---------------------------------------------------------------------------
# Load: persistence and report generation
# ---------------------------------------------------------------------------


def init_database(connection: sqlite3.Connection) -> None:
    """Ensure required tables exist in the SQLite database."""

    cursor = connection.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    connection.commit()


def persist_aggregates(
    connection: sqlite3.Connection,
    error_counts: Mapping[str, int],
    api_latency: Mapping[str, float],
    now: Optional[dt.datetime] = None,
) -> None:
    """Persist aggregated metrics into the SQLite database.

    Parameters
    ----------
    connection:
        Open SQLite connection.
    error_counts:
        Mapping of error message → count.
    api_latency:
        Mapping of endpoint → average latency in ms.
    now:
        Timestamp used for the ``dt`` columns. Defaults to ``datetime.utcnow()``.
    """

    if now is None:
        now = dt.datetime.utcnow()

    cursor = connection.cursor()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now.isoformat(), message, int(count)),
        )

    for endpoint, avg_ms in api_latency.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now.isoformat(), endpoint, float(avg_ms)),
        )

    connection.commit()


def render_html_report(
    error_counts: Mapping[str, int],
    api_latency: Mapping[str, float],
    active_sessions: int,
) -> str:
    """Render the HTML report with the same information as the original.

    The structure mirrors the original ``report.html`` output while using
    safer string handling.
    """

    lines: List[str] = []
    lines.append("<html>")
    lines.append("<head><title>System Report</title></head>")
    lines.append("<body>")

    # Error summary
    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for message, count in error_counts.items():
        lines.append(
            f"<li><b>{message}</b>: {int(count)} occurrences</li>"
        )
    lines.append("</ul>")

    # API latency table
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, avg in api_latency.items():
        lines.append(
            f"<tr><td>{endpoint}</td><td>{round(float(avg), 1)}</td></tr>"
        )
    lines.append("</table>")

    # Active sessions
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{int(active_sessions)} user(s) currently active</p>")

    lines.append("</body>")
    lines.append("</html>")

    return "\n".join(lines)


def write_report(html: str, output_path: Path = Path("report.html")) -> None:
    """Write the HTML report to ``output_path``."""

    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(config: Config) -> None:
    """Run the full ETL pipeline for a given configuration."""

    print(
        f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}..."
    )

    parsed = extract_logs(config.log_file)

    error_counts = aggregate_errors(parsed.errors)
    api_latency = aggregate_api_latency(parsed.api_calls)
    active_sessions = compute_active_sessions(parsed.user_events)

    connection = sqlite3.connect(str(config.db_path))
    try:
        init_database(connection)
        persist_aggregates(connection, error_counts, api_latency)
    finally:
        connection.close()

    html = render_html_report(error_counts, api_latency, active_sessions)
    write_report(html)

    print(f"Job finished at {dt.datetime.now()}")


def _bootstrap_demo_log_if_missing(log_path: Path) -> None:
    """Create a demo log file when none exists (for local testing).

    Mirrors the behaviour of the original script, which created a sample
    ``server.log`` file when missing.
    """

    if log_path.exists():
        return

    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]

    with log_path.open("w", encoding="utf-8") as f:
        f.writelines(sample_lines)


if __name__ == "__main__":
    cfg = load_config()
    _bootstrap_demo_log_if_missing(cfg.log_file)
    run_pipeline(cfg)
