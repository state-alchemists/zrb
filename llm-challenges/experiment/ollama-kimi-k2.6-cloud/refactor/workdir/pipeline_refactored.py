"""Server log processing pipeline.

Reads server logs, stores aggregated error and API latency metrics in SQLite,
and generates an HTML report.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict


# Pre-compiled regex patterns for log line parsing
_LOG_PATTERN_ERROR = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.+)$"
)
_LOG_PATTERN_WARN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.+)$"
)
_LOG_PATTERN_USER = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"INFO User (?P<user_id>\S+) (?P<action>.+)$"
)
_LOG_PATTERN_API = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"INFO API (?P<endpoint>\S+)(?: took (?P<duration>\d+)ms)?$"
)


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime configuration loaded from environment variables."""

    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str
    report_path: str


def load_config() -> PipelineConfig:
    """Load pipeline configuration from environment variables.

    Returns:
        A :class:`PipelineConfig` instance populated from ``os.environ``,
        falling back to sensible defaults for local development.
    """
    return PipelineConfig(
        db_path=os.getenv("DB_PATH", "metrics.db"),
        log_file=os.getenv("LOG_FILE", "server.log"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_user=os.getenv("DB_USER", "admin"),
        db_pass=os.getenv("DB_PASS", "password123"),
        report_path=os.getenv("REPORT_PATH", "report.html"),
    )


def extract_log_lines(log_file: str) -> list[str]:
    """Read all lines from the server log file.

    Args:
        log_file: Path to the server log file.

    Returns:
        A list of raw log lines with trailing newlines stripped.
        Returns an empty list if the file does not exist.
    """
    if not os.path.exists(log_file):
        return []
    with open(log_file, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


def transform_log_lines(
    lines: list[str],
) -> tuple[dict[str, int], dict[str, list[int]], dict[str, str]]:
    """Parse raw log lines into structured metrics.

    Uses regex to extract error messages, API latency samples, and session
    state transitions.

    Args:
        lines: Raw log lines from the server log.

    Returns:
        A three-tuple of:
        - **error_counts**: Mapping of error message to occurrence count.
        - **endpoint_latencies**: Mapping of API endpoint to a list of
          observed latencies in milliseconds.
        - **active_sessions**: Mapping of user ID to their most recent
          login timestamp.
    """
    error_counts: dict[str, int] = {}
    endpoint_latencies: DefaultDict[str, list[int]] = defaultdict(list)
    active_sessions: dict[str, str] = {}

    for line in lines:
        if not line:
            continue

        # ERROR
        m = _LOG_PATTERN_ERROR.match(line)
        if m:
            msg = m.group("message")
            error_counts[msg] = error_counts.get(msg, 0) + 1
            continue

        # WARN – tracked for parity, but not surfaced in downstream output
        if _LOG_PATTERN_WARN.match(line):
            continue

        # User session
        m = _LOG_PATTERN_USER.match(line)
        if m:
            user_id = m.group("user_id")
            action = m.group("action")
            timestamp = m.group("timestamp")
            if "logged in" in action:
                active_sessions[user_id] = timestamp
            elif "logged out" in action and user_id in active_sessions:
                active_sessions.pop(user_id)
            continue

        # API latency
        m = _LOG_PATTERN_API.match(line)
        if m:
            endpoint = m.group("endpoint")
            duration_str = m.group("duration")
            duration = int(duration_str) if duration_str is not None else 0
            endpoint_latencies[endpoint].append(duration)
            continue

    return error_counts, dict(endpoint_latencies), active_sessions


def load_metrics_to_db(
    db_path: str,
    error_counts: dict[str, int],
    endpoint_latencies: dict[str, list[int]],
) -> None:
    """Persist aggregated metrics into SQLite using parameterized queries.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Mapping of error message to occurrence count.
        endpoint_latencies: Mapping of endpoint to a list of latencies (ms).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")

    for msg, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, latencies in endpoint_latencies.items():
        avg_ms = sum(latencies) / len(latencies)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg_ms),
        )

    conn.commit()
    conn.close()


def generate_report(
    error_counts: dict[str, int],
    endpoint_latencies: dict[str, list[int]],
    active_session_count: int,
    report_path: str,
) -> None:
    """Generate an HTML report from the aggregated metrics.

    The report contains an error summary, an API latency table, and the
    number of currently active user sessions.

    Args:
        error_counts: Mapping of error message to occurrence count.
        endpoint_latencies: Mapping of endpoint to a list of latencies (ms).
        active_session_count: Number of currently active sessions.
        report_path: Output path for the generated HTML file.
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

    for ep, latencies in endpoint_latencies.items():
        avg = sum(latencies) / len(latencies)
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def ensure_sample_log(log_file: str) -> None:
    """Create a sample log file if none exists.

    Args:
        log_file: Path to the log file to seed.
    """
    if os.path.exists(log_file):
        return
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def run_pipeline(config: PipelineConfig) -> None:
    """Orchestrate the Extract-Transform-Load pipeline and report generation.

    Args:
        config: Pipeline configuration.
    """
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user} ...")

    # Extract
    lines = extract_log_lines(config.log_file)

    # Transform
    error_counts, endpoint_latencies, active_sessions = transform_log_lines(lines)

    # Load
    load_metrics_to_db(config.db_path, error_counts, endpoint_latencies)

    # Report
    generate_report(
        error_counts,
        endpoint_latencies,
        len(active_sessions),
        config.report_path,
    )

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    cfg = load_config()
    ensure_sample_log(cfg.log_file)
    run_pipeline(cfg)
