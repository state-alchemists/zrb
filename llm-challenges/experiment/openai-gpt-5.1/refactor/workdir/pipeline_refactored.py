import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


# Environment variable names
ENV_DB_PATH = "DB_PATH"
ENV_LOG_FILE = "LOG_FILE"
ENV_DB_HOST = "DB_HOST"
ENV_DB_PORT = "DB_PORT"
ENV_DB_USER = "DB_USER"
ENV_DB_PASS = "DB_PASS"
ENV_REPORT_FILE = "REPORT_FILE"


@dataclass
class LogContext:
    """In-memory representation of parsed log information.

    Attributes:
        error_counts: Mapping of error message to occurrence count.
        api_calls: Mapping of endpoint to list of call durations in ms.
        active_sessions: Mapping of user id to login timestamp string.
    """

    error_counts: Dict[str, int]
    api_calls: Dict[str, List[int]]
    active_sessions: Dict[str, str]


# Regular expressions for log parsing
BASE_LOG_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+" r"(?P<time>\d{2}:\d{2}:\d{2})\s+" r"(?P<level>\w+)\s+(?P<rest>.*)$"
)
USER_LOG_PATTERN = re.compile(r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)")
API_LOG_PATTERN = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+(?:.*?took\s+(?P<duration>\d+)ms)?",
    re.IGNORECASE,
)


def load_config_from_env() -> Tuple[Path, Path, str, int, str, str, Path]:
    """Load configuration from environment variables.

    Returns:
        Tuple containing database path, log file path, DB host, DB port,
        DB user, DB password, and report output path.

    Environment variables used:
        DB_PATH, LOG_FILE, DB_HOST, DB_PORT, DB_USER, DB_PASS, REPORT_FILE

    If a variable is not set, a sensible default matching the original
    script's behavior is used.
    """

    db_path = Path(os.getenv(ENV_DB_PATH, "metrics.db"))
    log_file = Path(os.getenv(ENV_LOG_FILE, "server.log"))
    db_host = os.getenv(ENV_DB_HOST, "localhost")

    try:
        db_port = int(os.getenv(ENV_DB_PORT, "5432"))
    except ValueError:
        db_port = 5432

    db_user = os.getenv(ENV_DB_USER, "admin")
    db_pass = os.getenv(ENV_DB_PASS, "password123")
    report_file = Path(os.getenv(ENV_REPORT_FILE, "report.html"))

    return db_path, log_file, db_host, db_port, db_user, db_pass, report_file


# -------------------- EXTRACT --------------------


def parse_log_lines(lines: Iterable[str]) -> LogContext:
    """Parse raw log lines into structured aggregates.

    This function encapsulates the "Extract" and part of the "Transform"
    phases for log parsing.

    The parsing logic is intentionally kept compatible with the original
    pipeline:
        - ERROR lines increment error message counts.
        - INFO User ... lines update session activity.
        - INFO API ... took Xms lines record API call durations.
        - WARN lines are ignored for aggregation (as in original DB writes).
    """

    error_counts: Dict[str, int] = {}
    api_calls: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        base_match = BASE_LOG_PATTERN.match(line)
        if not base_match:
            # Skip lines that do not match the expected base pattern
            continue

        dt_str = f"{base_match.group('date')} {base_match.group('time')}"
        level = base_match.group("level")
        rest = base_match.group("rest")

        if level == "ERROR":
            # Entire rest of the line is treated as the error message
            message = rest.strip()
            if not message:
                continue
            error_counts[message] = error_counts.get(message, 0) + 1

        elif level == "INFO":
            # User activity logs
            user_match = USER_LOG_PATTERN.search(rest)
            if user_match:
                user_id = user_match.group("user_id")
                action = user_match.group("action")

                if "logged in" in action:
                    active_sessions[user_id] = dt_str
                elif "logged out" in action and user_id in active_sessions:
                    active_sessions.pop(user_id, None)

                # No per-user aggregation was used later, only session count,
                # so we just maintain the active_sessions mapping.

            # API latency logs
            api_match = API_LOG_PATTERN.search(rest)
            if api_match:
                endpoint = api_match.group("endpoint")
                duration_str = api_match.group("duration") or "0"
                try:
                    duration = int(duration_str)
                except ValueError:
                    duration = 0

                api_calls.setdefault(endpoint, []).append(duration)

        # WARN and other levels are ignored for aggregation purposes

    return LogContext(
        error_counts=error_counts,
        api_calls=api_calls,
        active_sessions=active_sessions,
    )


def extract_from_log(log_path: Path) -> LogContext:
    """Extract structured metrics from a log file.

    Args:
        log_path: Path to the server log file.

    Returns:
        LogContext with aggregated metrics derived from the log.
    """

    if not log_path.exists():
        return LogContext(error_counts={}, api_calls={}, active_sessions={})

    with log_path.open("r", encoding="utf-8") as fh:
        return parse_log_lines(fh)


# -------------------- LOAD (DB) --------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create required tables if they do not exist."""

    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def load_metrics_into_db(conn: sqlite3.Connection, context: LogContext) -> None:
    """Persist aggregated metrics into the database using parameterized queries.

    Args:
        conn: Open SQLite connection.
        context: Parsed log metrics to persist.
    """

    cursor = conn.cursor()
    now_str = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")

    # Insert error summary
    for message, count in context.error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_str, message, count),
        )

    # Insert API metrics (average latency per endpoint)
    for endpoint, durations in context.api_calls.items():
        if not durations:
            continue
        avg_ms = sum(durations) / len(durations)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_str, endpoint, avg_ms),
        )

    conn.commit()


# -------------------- TRANSFORM + REPORT --------------------


def build_html_report(context: LogContext) -> str:
    """Generate the HTML report string from parsed metrics.

    The structure and content are preserved to match the original
    `report.html` output: error summary list, API latency table, and
    active session count.
    """

    # Error summary
    html_parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in context.error_counts.items():
        html_parts.append(
            f"<li><b>{err_msg}</b>: {count} occurrences</li>"
        )

    html_parts.append("</ul>")

    # API latency table
    html_parts.append("<h2>API Latency</h2>")
    html_parts.append("<table border='1'>")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for endpoint, durations in context.api_calls.items():
        if not durations:
            continue
        avg = sum(durations) / len(durations)
        html_parts.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )

    html_parts.append("</table>")

    # Active sessions
    html_parts.append("<h2>Active Sessions</h2>")
    html_parts.append(
        f"<p>{len(context.active_sessions)} user(s) currently active</p>"
    )

    html_parts.append("</body>")
    html_parts.append("</html>")

    # Join with newlines to match the original style as closely as needed
    return "\n".join(html_parts) + "\n"


# -------------------- ORCHESTRATION --------------------


def run_pipeline() -> None:
    """Run the full Extract → Transform → Load pipeline and write the report."""

    (
        db_path,
        log_file,
        db_host,
        db_port,
        db_user,
        db_pass,
        report_file,
    ) = load_config_from_env()

    # Log the (non-sensitive) connection info as before. Avoid logging the password.
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    # Extract & transform
    context = extract_from_log(log_file)

    # Load into DB with parameterized queries
    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)
        load_metrics_into_db(conn, context)
    finally:
        conn.close()

    # Build and write HTML report
    report_html = build_html_report(context)
    report_file.write_text(report_html, encoding="utf-8")

    print(f"Job finished at {datetime.datetime.now()}")


def _bootstrap_demo_log(log_file: Path) -> None:
    """Create a demo log file if one does not yet exist.

    This reproduces the behavior of the original script when invoked
    directly and no log file is present.
    """

    if log_file.exists():
        return

    demo_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]

    log_file.write_text("\n".join(demo_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    (
        _db_path,
        log_path,
        _db_host,
        _db_port,
        _db_user,
        _db_pass,
        _report_file,
    ) = load_config_from_env()

    _bootstrap_demo_log(log_path)
    run_pipeline()
