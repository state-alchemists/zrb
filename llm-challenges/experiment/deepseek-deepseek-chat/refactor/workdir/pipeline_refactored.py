"""
Server log processing pipeline.

Follows Extract → Transform → Load:
  - Extract:  parse raw log lines into structured records
  - Transform: aggregate errors, compute API latency stats, track sessions
  - Load:      write metrics to SQLite, render HTML report

All configuration comes from environment variables (see config()).
"""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config(NamedTuple):
    """Application configuration loaded from environment variables."""

    db_path: str
    log_path: str


def config() -> Config:
    """Load configuration from environment variables with sensible defaults.

    Required env vars: DB_PATH, LOG_FILE

    Returns:
        Config with validated paths.

    Raises:
        ValueError: if DB_PATH or LOG_FILE is unset.
    """
    db_path = os.environ.get("DB_PATH", "")
    log_path = os.environ.get("LOG_FILE", "")

    errors: list[str] = []
    if not db_path:
        errors.append("DB_PATH is not set")
    if not log_path:
        errors.append("LOG_FILE is not set")
    if errors:
        raise ValueError(
            "Missing required environment variable(s): " + "; ".join(errors)
        )

    return Config(db_path=db_path, log_path=log_path)


# ---------------------------------------------------------------------------
# Extract: log parsing
# ---------------------------------------------------------------------------

# Regex patterns for each log line format.
# Common pattern:  <timestamp>  <level>  <message>
_PATTERN_ERROR = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+ERROR\s+(.+)$"
)
_PATTERN_WARN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+WARN\s+(.+)$"
)
_PATTERN_USER = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+INFO\s+User\s+(\S+)\s+(.+)$"
)
_PATTERN_API = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+INFO\s+API\s+(\S+)\s+took\s+(\d+)ms$"
)


class ErrorRecord(NamedTuple):
    timestamp: str
    message: str


class WarnRecord(NamedTuple):
    timestamp: str
    message: str


class UserRecord(NamedTuple):
    timestamp: str
    user_id: str
    action: str


class ApiRecord(NamedTuple):
    timestamp: str
    endpoint: str
    duration_ms: int


def parse_log_line(line: str) -> ErrorRecord | WarnRecord | UserRecord | ApiRecord | None:
    """Parse a single log line into a typed record.

    Args:
        line: A raw log line.

    Returns:
        A record for recognised line formats, or *None* for unrecognised lines.
    """
    line = line.rstrip("\n")

    m = _PATTERN_ERROR.match(line)
    if m:
        return ErrorRecord(timestamp=m.group(1), message=m.group(2).strip())

    m = _PATTERN_WARN.match(line)
    if m:
        return WarnRecord(timestamp=m.group(1), message=m.group(2).strip())

    m = _PATTERN_USER.match(line)
    if m:
        return UserRecord(timestamp=m.group(1), user_id=m.group(2), action=m.group(3).strip())

    m = _PATTERN_API.match(line)
    if m:
        return ApiRecord(
            timestamp=m.group(1),
            endpoint=m.group(2),
            duration_ms=int(m.group(3)),
        )

    return None


def extract(log_path: str) -> list[ErrorRecord | WarnRecord | UserRecord | ApiRecord]:
    """Read and parse every line from the log file.

    Args:
        log_path: Path to the server log file.

    Returns:
        A list of typed records (one per successfully parsed line).
    """
    records: list[ErrorRecord | WarnRecord | UserRecord | ApiRecord] = []

    if not os.path.exists(log_path):
        return records

    with open(log_path, "r") as f:
        for line in f:
            record = parse_log_line(line)
            if record is not None:
                records.append(record)

    return records


# ---------------------------------------------------------------------------
# Transform: aggregate records into derived data
# ---------------------------------------------------------------------------

class ErrorSummary(NamedTuple):
    """Aggregated error count."""

    message: str
    count: int


class ApiLatencySummary(NamedTuple):
    """Aggregated API latency."""

    endpoint: str
    avg_ms: float


class TransformResult(NamedTuple):
    """Output of the transform step."""

    error_summary: list[ErrorSummary]
    api_latency: list[ApiLatencySummary]
    active_session_count: int


def _build_session_map(
    records: list[ErrorRecord | WarnRecord | UserRecord | ApiRecord],
) -> dict[str, int]:
    """Compute active login sessions from user records.

    Args:
        records: Parsed log records.

    Returns:
        Map of user_id -> session count (0 or 1 per user).
    """
    sessions: dict[str, str] = {}

    for r in records:
        if isinstance(r, UserRecord):
            if "logged in" in r.action:
                sessions[r.user_id] = r.timestamp
            elif "logged out" in r.action and r.user_id in sessions:
                del sessions[r.user_id]

    return sessions


def transform(
    records: list[ErrorRecord | WarnRecord | UserRecord | ApiRecord],
) -> TransformResult:
    """Derive error counts, API latency stats, and active session count.

    Args:
        records: Parsed log records from *extract()*.

    Returns:
        A *TransformResult* containing aggregated data.
    """
    # --- Error aggregation ---
    error_counts: dict[str, int] = defaultdict(int)
    for r in records:
        if isinstance(r, ErrorRecord):
            error_counts[r.message] += 1

    error_summary = [
        ErrorSummary(message=msg, count=c) for msg, c in error_counts.items()
    ]
    error_summary.sort(key=lambda x: x.message)

    # --- API latency aggregation ---
    endpoint_times: dict[str, list[int]] = defaultdict(list)
    for r in records:
        if isinstance(r, ApiRecord):
            endpoint_times[r.endpoint].append(r.duration_ms)

    api_latency = [
        ApiLatencySummary(endpoint=ep, avg_ms=sum(times) / len(times))
        for ep, times in endpoint_times.items()
    ]
    api_latency.sort(key=lambda x: x.endpoint)

    # --- Active session count ---
    sessions = _build_session_map(records)
    active_session_count = len(sessions)

    return TransformResult(
        error_summary=error_summary,
        api_latency=api_latency,
        active_session_count=active_session_count,
    )


# ---------------------------------------------------------------------------
# Load: SQLite & HTML report
# ---------------------------------------------------------------------------

def _init_db(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection and ensure tables exist.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open connection (caller must close).
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    return conn


def _load_db(
    conn: sqlite3.Connection,
    error_summary: list[ErrorSummary],
    api_latency: list[ApiLatencySummary],
) -> None:
    """Write aggregated metrics into database tables.

    Uses parameterized queries — no SQL injection risk.

    Args:
        conn: Open SQLite connection.
        error_summary: Aggregated error data.
        api_latency: Aggregated API latency data.
    """
    now = datetime.datetime.now().isoformat()

    for item in error_summary:
        conn.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, item.message, item.count),
        )

    for item in api_latency:
        conn.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, item.endpoint, item.avg_ms),
        )

    conn.commit()


def _render_html(result: TransformResult) -> str:
    """Generate the HTML report string from transformed data.

    Args:
        result: Transformed data.

    Returns:
        A complete HTML document.
    """
    lines: list[str] = []

    lines.append("<!DOCTYPE html>")
    lines.append("<html>")
    lines.append("<head><meta charset='utf-8'><title>System Report</title></head>")
    lines.append("<body>")

    # Error summary
    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for item in result.error_summary:
        lines.append(
            f"<li><b>{_escape_html(item.message)}</b>: "
            f"{item.count} occurrences</li>"
        )
    lines.append("</ul>")

    # API latency table
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for item in result.api_latency:
        lines.append(
            f"<tr><td>{_escape_html(item.endpoint)}</td>"
            f"<td>{item.avg_ms:.1f}</td></tr>"
        )
    lines.append("</table>")

    # Active sessions
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{result.active_session_count} user(s) currently active</p>")

    lines.append("</body>")
    lines.append("</html>")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for safe interpolation.

    Args:
        text: Raw string that may contain HTML special characters.

    Returns:
        Escaped string safe for use in HTML content.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load(
    result: TransformResult,
    db_path: str,
    report_path: str,
) -> None:
    """Write transformed data to SQLite and render the HTML report.

    Args:
        result: Transformed data to persist.
        db_path: Path to the SQLite database.
        report_path: Path for the output HTML report.
    """
    conn = _init_db(db_path)
    try:
        _load_db(conn, result.error_summary, result.api_latency)
    finally:
        conn.close()

    html = _render_html(result)
    with open(report_path, "w") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(db_path: str, log_path: str, report_path: str = "report.html") -> None:
    """Execute the full Extract → Transform → Load pipeline.

    Args:
        db_path: Path to the SQLite database file.
        log_path: Path to the server log file.
        report_path: Path for the generated HTML report (default: report.html).
    """
    print(f"[pipeline] Extracting records from {log_path} ...")
    records = extract(log_path)

    print(f"[pipeline] Transforming {len(records)} record(s) ...")
    result = transform(records)

    print(f"[pipeline] Loading results into {db_path} and {report_path} ...")
    load(result, db_path, report_path)

    print(f"[pipeline] Done at {datetime.datetime.now().isoformat()}")


def main() -> None:
    """Entry point: load config and run the pipeline."""
    cfg = config()
    run_pipeline(db_path=cfg.db_path, log_path=cfg.log_path)


if __name__ == "__main__":
    main()
