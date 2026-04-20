"""Server-log processing pipeline: extract, transform, load.

Reads server logs, computes error summaries / API latency / active-session
counts, persists metrics to SQLite, and writes an HTML report.

All configuration is read from environment variables with sensible defaults.
No credentials or paths are hardcoded.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration — all sourced from environment variables
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: str = os.getenv("LOG_DB_PATH", "metrics.db")
    log_file: str = os.getenv("LOG_FILE", "server.log")
    report_path: str = os.getenv("LOG_REPORT_PATH", "report.html")
    db_host: str = os.getenv("LOG_DB_HOST", "localhost")
    db_port: int = int(os.getenv("LOG_DB_PORT", "5432"))
    db_user: str = os.getenv("LOG_DB_USER", "")
    db_pass: str = os.getenv("LOG_DB_PASS", "")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ErrorEntry:
    """A single error-level log event."""
    timestamp: str
    message: str


@dataclass
class ApiCall:
    """A single API call latency record."""
    timestamp: str
    endpoint: str
    latency_ms: int


@dataclass
class UserEvent:
    """A user login/logout event."""
    timestamp: str
    user_id: str
    action: str


@dataclass
class WarningEntry:
    """A single warning-level log event."""
    timestamp: str
    message: str


@dataclass
class ParsedLog:
    """Aggregate container for all parsed log records."""
    errors: List[ErrorEntry] = field(default_factory=list)
    api_calls: List[ApiCall] = field(default_factory=list)
    user_events: List[UserEvent] = field(default_factory=list)
    warnings: List[WarningEntry] = field(default_factory=list)


@dataclass
class TransformedMetrics:
    """Aggregated metrics ready for storage and reporting."""
    error_counts: Dict[str, int] = field(default_factory=dict)
    api_latency: Dict[str, List[int]] = field(default_factory=dict)
    active_sessions: int = 0


# ---------------------------------------------------------------------------
# Log-line patterns (compiled once at module level)
# ---------------------------------------------------------------------------

# General structure: "2024-01-01 12:00:00 LEVEL ..."
_TIMESTAMP = r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
_LEVEL = r"(?P<level>INFO|ERROR|WARN)"
_BASE = rf"^{_TIMESTAMP} {_LEVEL}\s+(?P<rest>.*)$"

RE_LOG_LINE = re.compile(_BASE)

# INFO User <uid> <action>
RE_USER_EVENT = re.compile(
    r"^User (?P<uid>\S+)\s+(?P<action>.+)$"
)

# INFO API <endpoint> took <n>ms
RE_API_CALL = re.compile(
    r"^API (?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?$"
)


# ---------------------------------------------------------------------------
# EXTRACT — read raw log lines from file
# ---------------------------------------------------------------------------

def extract_log_lines(log_file: str) -> List[str]:
    """Read and return all lines from the log file.

    Args:
        log_file: Path to the server log file.

    Returns:
        List of raw log lines (including trailing newlines).
        Returns an empty list if the file does not exist.
    """
    path = Path(log_file)
    if not path.exists():
        return []
    return path.read_text().splitlines()


# ---------------------------------------------------------------------------
# TRANSFORM — parse lines into structured data, then aggregate
# ---------------------------------------------------------------------------

def parse_log_lines(lines: List[str]) -> ParsedLog:
    """Parse raw log lines into structured records.

    Uses regex patterns to robustly extract fields from each line type
    (ERROR, WARN, INFO/User, INFO/API).

    Args:
        lines: Raw log lines (without trailing newlines).

    Returns:
        A ParsedLog containing categorized records.
    """
    result = ParsedLog()

    for line in lines:
        match = RE_LOG_LINE.match(line)
        if not match:
            continue

        ts = match.group("ts")
        level = match.group("level")
        rest = match.group("rest")

        if level == "ERROR":
            result.errors.append(ErrorEntry(timestamp=ts, message=rest))

        elif level == "WARN":
            result.warnings.append(WarningEntry(timestamp=ts, message=rest))

        elif level == "INFO":
            # Try user-event pattern first
            user_match = RE_USER_EVENT.match(rest)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                result.user_events.append(
                    UserEvent(timestamp=ts, user_id=uid, action=action)
                )
                continue

            # Try API-call pattern
            api_match = RE_API_CALL.match(rest)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms") or 0)
                result.api_calls.append(
                    ApiCall(timestamp=ts, endpoint=endpoint, latency_ms=ms)
                )

    return result


def compute_metrics(parsed: ParsedLog) -> TransformedMetrics:
    """Aggregate parsed log records into summary metrics.

    - error_counts:  mapping of error message → occurrence count
    - api_latency:    mapping of endpoint → list of latency values
    - active_sessions: count of users logged in but not yet logged out

    Args:
        parsed: Categorized log records.

    Returns:
        Aggregated metrics ready for storage and reporting.
    """
    # Error counts
    error_counts: Dict[str, int] = {}
    for err in parsed.errors:
        error_counts[err.message] = error_counts.get(err.message, 0) + 1

    # API latency per endpoint
    api_latency: Dict[str, List[int]] = {}
    for call in parsed.api_calls:
        api_latency.setdefault(call.endpoint, []).append(call.latency_ms)

    # Active sessions: track login → logout, count remaining
    active_sessions: Dict[str, str] = {}  # uid → login timestamp
    for ev in parsed.user_events:
        if "logged in" in ev.action:
            active_sessions[ev.user_id] = ev.timestamp
        elif "logged out" in ev.action and ev.user_id in active_sessions:
            del active_sessions[ev.user_id]

    return TransformedMetrics(
        error_counts=error_counts,
        api_latency=api_latency,
        active_sessions=len(active_sessions),
    )


# ---------------------------------------------------------------------------
# LOAD — persist to SQLite and write HTML report
# ---------------------------------------------------------------------------

def load_to_database(
    metrics: TransformedMetrics,
    config: Config,
) -> None:
    """Insert aggregated metrics into SQLite using parameterized queries.

    Creates the target tables if they do not already exist.

    Args:
        metrics: Aggregated metrics to persist.
        config: Runtime configuration (provides db_path, db_host, etc.).
    """
    now = datetime.datetime.now().isoformat()

    print(
        f"Connecting to {config.db_host}:{config.db_port}"
        f" as {config.db_user or '<no-user>'}..."
    )

    conn = sqlite3.connect(config.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        for msg, count in metrics.error_counts.items():
            cursor.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (now, msg, count),
            )

        for ep, times in metrics.api_latency.items():
            avg = sum(times) / len(times)
            cursor.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (now, ep, avg),
            )

        conn.commit()
    finally:
        conn.close()


def generate_report(metrics: TransformedMetrics, report_path: str) -> None:
    """Write an HTML report summarizing errors, API latency, and sessions.

    Args:
        metrics: Aggregated metrics to render.
        report_path: File path for the output HTML report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in metrics.error_counts.items():
        lines.append(
            f"<li><b>{err_msg}</b>: {count} occurrences</li>"
        )

    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for ep, times in metrics.api_latency.items():
        avg = round(sum(times) / len(times), 1)
        lines.append(f"<tr><td>{ep}</td><td>{avg}</td></tr>")

    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{metrics.active_sessions} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    Path(report_path).write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(config: Optional[Config] = None) -> None:
    """Execute the full Extract → Transform → Load pipeline.

    Args:
        config: Optional configuration; defaults to env-var-based Config().
    """
    if config is None:
        config = Config()

    # Extract
    lines = extract_log_lines(config.log_file)

    # Transform
    parsed = parse_log_lines(lines)
    metrics = compute_metrics(parsed)

    # Load
    load_to_database(metrics, config)
    generate_report(metrics, config.report_path)

    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Seed data for first run (mirrors original sample data)
# ---------------------------------------------------------------------------

SAMPLE_LOG_LINES = [
    "2024-01-01 12:00:00 INFO User 42 logged in",
    "2024-01-01 12:05:00 ERROR Database timeout",
    "2024-01-01 12:05:05 ERROR Database timeout",
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
    "2024-01-01 12:09:00 WARN Memory usage at 87%",
    "2024-01-01 12:10:00 INFO User 42 logged out",
]


def seed_sample_log(log_file: str) -> None:
    """Write sample log data if the log file does not already exist."""
    if not Path(log_file).exists():
        Path(log_file).write_text("\n".join(SAMPLE_LOG_LINES) + "\n")


if __name__ == "__main__":
    seed_sample_log(os.getenv("LOG_FILE", "server.log"))
    run_pipeline()