"""Server log processing pipeline with ETL architecture.

Extracts log entries, transforms them into metrics, and loads into SQLite.
Generates an HTML report with error summary, API latency, and active sessions.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: str
    log_file: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables with defaults."""
        return cls(
            db_path=os.getenv("DB_PATH", "metrics.db"),
            log_file=os.getenv("LOG_FILE", "server.log"),
        )


@dataclass
class ErrorEntry:
    """Represents an error log entry."""

    timestamp: str
    message: str


@dataclass
class UserAction:
    """Represents a user session action."""

    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """Represents an API call with latency."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class LogData:
    """Aggregated log data after extraction and transformation."""

    errors: list[ErrorEntry] = field(default_factory=list)
    user_actions: list[UserAction] = field(default_factory=list)
    api_calls: list[ApiCall] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Regex patterns for log parsing
_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<message>.+)$"
)
_USER_PATTERN = re.compile(r"User (?P<user_id>\S+) (?P<action>.+)$")
_API_PATTERN = re.compile(r"API (?P<endpoint>\S+).*took (?P<duration>\d+)ms")


def extract_log_entries(log_file: str) -> LogData:
    """Parse log file and extract structured entries.

    Args:
        log_file: Path to the log file.

    Returns:
        LogData with parsed errors, user actions, and API calls.
    """
    data = LogData()

    if not os.path.exists(log_file):
        return data

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            match = _LOG_PATTERN.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            message = match.group("message")

            if level == "ERROR":
                data.errors.append(ErrorEntry(timestamp=timestamp, message=message))
            elif level == "WARN":
                data.warnings.append(message)
            elif level == "INFO":
                user_match = _USER_PATTERN.search(message)
                if user_match:
                    data.user_actions.append(
                        UserAction(
                            timestamp=timestamp,
                            user_id=user_match.group("user_id"),
                            action=user_match.group("action").strip(),
                        )
                    )
                    continue

                api_match = _API_PATTERN.search(message)
                if api_match:
                    data.api_calls.append(
                        ApiCall(
                            timestamp=timestamp,
                            endpoint=api_match.group("endpoint"),
                            duration_ms=int(api_match.group("duration")),
                        )
                    )

    return data


def transform_error_counts(errors: list[ErrorEntry]) -> dict[str, int]:
    """Aggregate error counts by message.

    Args:
        errors: List of error entries.

    Returns:
        Dictionary mapping error message to occurrence count.
    """
    counts: dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1
    return counts


def transform_api_stats(api_calls: list[ApiCall]) -> dict[str, float]:
    """Calculate average latency per API endpoint.

    Args:
        api_calls: List of API call entries.

    Returns:
        Dictionary mapping endpoint to average latency in milliseconds.
    """
    endpoint_times: dict[str, list[int]] = {}
    for call in api_calls:
        endpoint_times.setdefault(call.endpoint, []).append(call.duration_ms)

    return {
        endpoint: sum(times) / len(times)
        for endpoint, times in endpoint_times.items()
    }


def transform_active_sessions(user_actions: list[UserAction]) -> set[str]:
    """Track currently active user sessions.

    Args:
        user_actions: List of user action entries.

    Returns:
        Set of user IDs currently logged in.
    """
    sessions: set[str] = set()
    for action in user_actions:
        if "logged in" in action.action:
            sessions.add(action.user_id)
        elif "logged out" in action.action:
            sessions.discard(action.user_id)
    return sessions


def load_to_database(
    conn: sqlite3.Connection,
    error_counts: dict[str, int],
    api_stats: dict[str, float],
) -> None:
    """Insert aggregated metrics into database using parameterized queries.

    Args:
        conn: SQLite database connection.
        error_counts: Error message to count mapping.
        api_stats: Endpoint to average latency mapping.
    """
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count),
        )

    for endpoint, avg_ms in api_stats.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, avg_ms),
        )

    conn.commit()


def generate_report(
    error_counts: dict[str, int],
    api_stats: dict[str, float],
    active_sessions: set[str],
    output_path: str,
) -> None:
    """Generate HTML report with metrics.

    Args:
        error_counts: Error message to count mapping.
        api_stats: Endpoint to average latency mapping.
        active_sessions: Set of active user IDs.
        output_path: Path to write the HTML report.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for message, count in sorted(error_counts.items(), key=lambda x: -x[1]):
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")

    lines.extend(["</ul>", "<h2>API Latency</h2>", "<table border='1'>"])
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for endpoint, avg_ms in sorted(api_stats.items()):
        lines.append(f"<tr><td>{endpoint}</td><td>{avg_ms:.1f}</td></tr>")

    lines.extend(["</table>", "<h2>Active Sessions</h2>"])
    lines.append(f"<p>{len(active_sessions)} user(s) currently active</p>")
    lines.extend(["</body>", "</html>"])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_pipeline(config: Optional[Config] = None) -> None:
    """Execute the complete ETL pipeline.

    Args:
        config: Pipeline configuration. If None, loads from environment.
    """
    if config is None:
        config = Config.from_env()

    # Extract
    log_data = extract_log_entries(config.log_file)

    # Transform
    error_counts = transform_error_counts(log_data.errors)
    api_stats = transform_api_stats(log_data.api_calls)
    active_sessions = transform_active_sessions(log_data.user_actions)

    # Load
    conn = sqlite3.connect(config.db_path)
    try:
        load_to_database(conn, error_counts, api_stats)
    finally:
        conn.close()

    # Report
    generate_report(error_counts, api_stats, active_sessions, "report.html")

    print(f"Pipeline completed at {datetime.datetime.now()}")


def _create_sample_log_file(path: str) -> None:
    """Create a sample log file for testing."""
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sample_lines) + "\n")


if __name__ == "__main__":
    config = Config.from_env()
    if not os.path.exists(config.log_file):
        _create_sample_log_file(config.log_file)
    run_pipeline(config)