"""Log processing pipeline: Extract → Transform → Load.

Reads server logs, extracts structured data via regex, stores in SQLite
with parameterized queries, and produces an HTML summary report.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# Register sqlite3 datetime adapter (Python 3.12+ compliant).
def _adapt_datetime(val: datetime.datetime) -> str:
    return val.isoformat()


sqlite3.register_adapter(datetime.datetime, _adapt_datetime)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Immutable configuration loaded from environment variables."""

    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "metrics.db"))
    log_path: str = field(default_factory=lambda: os.getenv("LOG_PATH", "server.log"))
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(
        default_factory=lambda: int(os.getenv("DB_PORT", "5432"))
    )
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "admin"))
    db_pass: str = field(default_factory=lambda: os.getenv("DB_PASS", "password123"))


def load_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        Config populated from environment, falling back to defaults.
    """
    return Config()


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def extract(config: Config) -> List[str]:
    """Read log lines from the configured log file.

    Args:
        config: Application configuration with log path.

    Returns:
        List of raw log lines. Empty list if the file does not exist.
    """
    if not os.path.exists(config.log_path):
        return []
    with open(config.log_path, "r") as f:
        return [line.rstrip("\n") for line in f]


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

# Compiled regex patterns for each log line variant.
_PATTERNS = {
    "error": re.compile(
        r"^(?P<dt>\S+ \S+) ERROR (?P<message>.+)$"
    ),
    "user": re.compile(
        r"^(?P<dt>\S+ \S+) INFO User (?P<uid>\S+) (?P<action>.+)$"
    ),
    "api": re.compile(
        r"^(?P<dt>\S+ \S+) INFO API (?P<endpoint>\S+) took (?P<ms>\d+)ms$"
    ),
    "warn": re.compile(
        r"^(?P<dt>\S+ \S+) WARN (?P<message>.+)$"
    ),
}


@dataclass
class ParseResult:
    """Structured result of parsing log lines."""

    error_counts: Dict[str, int] = field(default_factory=dict)
    api_calls: List[Dict[str, object]] = field(default_factory=list)


def _parse_line(
    line: str, sessions: Dict[str, str], result: ParseResult
) -> None:
    """Parse a single log line and update result/session state in-place.

    Args:
        line: Raw log line.
        sessions: Mutable mapping of user-id → session-start-timestamp.
        result: Mutable ParseResult updated with parsed data.
    """
    m = _PATTERNS["error"].match(line)
    if m:
        msg = m.group("message")
        result.error_counts[msg] = result.error_counts.get(msg, 0) + 1
        return

    m = _PATTERNS["user"].match(line)
    if m:
        uid = m.group("uid")
        action = m.group("action")
        if "logged in" in action:
            sessions[uid] = m.group("dt")
        elif "logged out" in action and uid in sessions:
            del sessions[uid]
        return

    m = _PATTERNS["api"].match(line)
    if m:
        result.api_calls.append({
            "dt": m.group("dt"),
            "endpoint": m.group("endpoint"),
            "ms": int(m.group("ms")),
        })
        return

    m = _PATTERNS["warn"].match(line)
    if m:
        # Warnings are acknowledged but not aggregated in the report.
        return


def transform(lines: List[str]) -> Tuple[Dict[str, int], List[Dict[str, object]], Dict[str, str]]:
    """Parse raw log lines into structured summaries.

    Args:
        lines: Raw log lines.

    Returns:
        Tuple of (error_counts, api_calls, active_sessions).
    """
    sessions: Dict[str, str] = {}
    result = ParseResult()

    for line in lines:
        _parse_line(line, sessions, result)

    return result.error_counts, result.api_calls, sessions


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def _init_db(conn: sqlite3.Connection) -> None:
    """Create database tables if they do not exist.

    Args:
        conn: Open SQLite connection.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def _store_errors(conn: sqlite3.Connection, error_counts: Dict[str, int]) -> None:
    """Insert error summary rows using parameterized queries.

    Args:
        conn: Open SQLite connection.
        error_counts: Mapping of error message → occurrence count.
    """
    now = datetime.datetime.now()
    for msg, count in error_counts.items():
        conn.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )


def _store_api_metrics(
    conn: sqlite3.Connection, api_calls: List[Dict[str, object]]
) -> None:
    """Aggregate API latencies and insert averages using parameterized queries.

    Args:
        conn: Open SQLite connection.
        api_calls: List of parsed API call records.
    """
    endpoint_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        ep = str(call["endpoint"])
        endpoint_stats.setdefault(ep, []).append(int(call["ms"]))

    now = datetime.datetime.now()
    for ep, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        conn.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg),
        )


def _build_html_report(
    error_counts: Dict[str, int],
    api_calls: List[Dict[str, object]],
    sessions: Dict[str, str],
) -> str:
    """Generate an HTML report string from the processed data.

    Args:
        error_counts: Error message → count.
        api_calls: Parsed API call records.
        sessions: Current active sessions (user-id → timestamp).

    Returns:
        Complete HTML document as a string.
    """
    endpoint_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        ep = str(call["endpoint"])
        endpoint_stats.setdefault(ep, []).append(int(call["ms"]))

    parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1><ul>",
    ]
    for err_msg, count in error_counts.items():
        parts.append(
            f"<li><b>{err_msg}</b>: {count} occurrences</li>"
        )
    parts.append("</ul>")

    parts.append("<h2>API Latency</h2><table border='1'>")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        parts.append(
            f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{len(sessions)} user(s) currently active</p>")
    parts.append("</body>\n</html>")

    return "\n".join(parts)


def load(
    config: Config,
    error_counts: Dict[str, int],
    api_calls: List[Dict[str, object]],
    sessions: Dict[str, str],
) -> None:
    """Persist data to SQLite and write the HTML report.

    Args:
        config: Application configuration.
        error_counts: Error message → occurrence count.
        api_calls: Parsed API call records.
        sessions: Current active sessions.
    """
    print(
        f"Connecting to {config.db_host}:{config.db_port} "
        f"as {config.db_user}..."
    )

    conn = sqlite3.connect(config.db_path)
    try:
        _init_db(conn)
        _store_errors(conn, error_counts)
        _store_api_metrics(conn, api_calls)
        conn.commit()
    finally:
        conn.close()

    html = _build_html_report(error_counts, api_calls, sessions)
    with open("report.html", "w") as f:
        f.write(html)
    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Sample data (mirrors original __main__ behaviour)
# ---------------------------------------------------------------------------

_SAMPLE_LINES = [
    "2024-01-01 12:00:00 INFO User 42 logged in",
    "2024-01-01 12:05:00 ERROR Database timeout",
    "2024-01-01 12:05:05 ERROR Database timeout",
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
    "2024-01-01 12:09:00 WARN Memory usage at 87%",
    "2024-01-01 12:10:00 INFO User 42 logged out",
]


def _ensure_sample_log(config: Config) -> None:
    """Write sample log lines if the log file does not exist.

    Args:
        config: Application configuration with log path.
    """
    if not os.path.exists(config.log_path):
        with open(config.log_path, "w") as f:
            for line in _SAMPLE_LINES:
                f.write(line + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full ETL pipeline: extract, transform, and load."""
    config = load_config()
    _ensure_sample_log(config)

    lines = extract(config)
    if not lines:
        print("No log file found — nothing to process.")
        return

    error_counts, api_calls, sessions = transform(lines)
    load(config, error_counts, api_calls, sessions)


if __name__ == "__main__":
    main()
