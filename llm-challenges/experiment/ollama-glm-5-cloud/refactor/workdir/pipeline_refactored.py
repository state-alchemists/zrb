"""Server log processing pipeline with ETL architecture.

Extracts log entries, transforms them into metrics, loads to database,
and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Config:
    """Configuration loaded from environment variables."""
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "metrics.db"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "server.log"))
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "admin"))


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
    """Represents an API call metrics entry."""
    timestamp: str
    endpoint: str
    latency_ms: int


@dataclass
class LogData:
    """Container for all extracted log data."""
    errors: List[ErrorEntry] = field(default_factory=list)
    user_actions: List[UserAction] = field(default_factory=list)
    api_calls: List[ApiCall] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)


# Regex patterns for log parsing
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|ERROR|WARN) "
    r"(?P<message>.*)$"
)

USER_ACTION_PATTERN = re.compile(
    r"User (?P<user_id>\S+) (?P<action>.+)"
)

API_CALL_PATTERN = re.compile(
    r"API (?P<endpoint>\S+) took (?P<latency>\d+)ms"
)


def extract_log_entries(log_file_path: str) -> LogData:
    """Parse log file and extract structured entries.

    Args:
        log_file_path: Path to the server log file.

    Returns:
        LogData containing all parsed entries.
    """
    log_data = LogData()

    if not os.path.exists(log_file_path):
        return log_data

    with open(log_file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = LOG_PATTERN.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            message = match.group("message")

            if level == "ERROR":
                log_data.errors.append(ErrorEntry(timestamp=timestamp, message=message))

            elif level == "WARN":
                log_data.warnings.append({"timestamp": timestamp, "message": message})

            elif level == "INFO":
                user_match = USER_ACTION_PATTERN.search(message)
                if user_match:
                    log_data.user_actions.append(
                        UserAction(
                            timestamp=timestamp,
                            user_id=user_match.group("user_id"),
                            action=user_match.group("action").strip()
                        )
                    )
                    continue

                api_match = API_CALL_PATTERN.search(message)
                if api_match:
                    log_data.api_calls.append(
                        ApiCall(
                            timestamp=timestamp,
                            endpoint=api_match.group("endpoint"),
                            latency_ms=int(api_match.group("latency"))
                        )
                    )

    return log_data


def transform_error_counts(errors: List[ErrorEntry]) -> Dict[str, int]:
    """Aggregate error counts by message.

    Args:
        errors: List of error entries.

    Returns:
        Dictionary mapping error messages to occurrence counts.
    """
    counts: Dict[str, int] = {}
    for error in errors:
        counts[error.message] = counts.get(error.message, 0) + 1
    return counts


def transform_api_metrics(api_calls: List[ApiCall]) -> Dict[str, float]:
    """Calculate average latency per endpoint.

    Args:
        api_calls: List of API call entries.

    Returns:
        Dictionary mapping endpoints to average latency in ms.
    """
    latencies: Dict[str, List[int]] = {}
    for call in api_calls:
        latencies.setdefault(call.endpoint, []).append(call.latency_ms)

    return {
        endpoint: sum(times) / len(times)
        for endpoint, times in latencies.items()
    }


def transform_active_sessions(user_actions: List[UserAction]) -> int:
    """Calculate current active session count.

    Args:
        user_actions: List of user action entries.

    Returns:
        Number of currently active sessions.
    """
    sessions: Dict[str, str] = {}
    for action in user_actions:
        if "logged in" in action.action.lower():
            sessions[action.user_id] = action.timestamp
        elif "logged out" in action.action.lower() and action.user_id in sessions:
            sessions.pop(action.user_id)

    return len(sessions)


def load_to_database(
    db_path: str,
    error_counts: Dict[str, int],
    api_metrics: Dict[str, float]
) -> None:
    """Load transformed metrics into SQLite database.

    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Error message counts.
        api_metrics: Endpoint latency averages.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    timestamp = datetime.datetime.now().isoformat()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, message, count)
        )

    for endpoint, avg_ms in api_metrics.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_ms)
        )

    conn.commit()
    conn.close()


def generate_report(
    error_counts: Dict[str, int],
    api_metrics: Dict[str, float],
    active_sessions: int
) -> str:
    """Generate HTML report from metrics.

    Args:
        error_counts: Error message counts.
        api_metrics: Endpoint latency averages.
        active_sessions: Number of active user sessions.

    Returns:
        HTML string for the report.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]

    for message, count in error_counts.items():
        lines.append(f"<li><b>{message}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])

    for endpoint, avg_ms in api_metrics.items():
        lines.append(f"<tr><td>{endpoint}</td><td>{avg_ms:.1f}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    return "\n".join(lines)


def run_pipeline(config: Optional[Config] = None) -> None:
    """Execute the full ETL pipeline.

    Args:
        config: Optional configuration object. Uses defaults if not provided.
    """
    if config is None:
        config = Config()

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    # Extract
    log_data = extract_log_entries(config.log_file)

    # Transform
    error_counts = transform_error_counts(log_data.errors)
    api_metrics = transform_api_metrics(log_data.api_calls)
    active_sessions = transform_active_sessions(log_data.user_actions)

    # Load
    load_to_database(config.db_path, error_counts, api_metrics)

    # Report
    report_html = generate_report(error_counts, api_metrics, active_sessions)
    with open("report.html", "w") as f:
        f.write(report_html)

    print(f"Job finished at {datetime.datetime.now()}")


def create_sample_log_file(path: str) -> None:
    """Create a sample log file for testing.

    Args:
        path: Path where the sample log file will be created.
    """
    with open(path, "w") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


if __name__ == "__main__":
    config = Config()
    if not os.path.exists(config.log_file):
        create_sample_log_file(config.log_file)
    run_pipeline(config)