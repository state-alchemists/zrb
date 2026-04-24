"""Server-log processing pipeline: Extract → Transform → Load.

Parses server logs, aggregates error counts / API latencies / active sessions,
persists results to SQLite, and writes an HTML report.

All configuration is read from environment variables with sensible defaults:
    DB_PATH   – path to the SQLite database          (default: "metrics.db")
    LOG_FILE  – path to the server log file            (default: "server.log")
    DB_HOST   – database host, logged for auditing    (default: "localhost")
    DB_PORT   – database port, logged for auditing     (default: "5432")
    DB_USER   – database user, logged for auditing     (default: "admin")
    DB_PASS   – database password, logged for auditing  (default: "password123")
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _env(key: str, default: str) -> str:
    """Read an environment variable, falling back to *default*."""
    return os.environ.get(key, default)


DB_PATH: str = _env("DB_PATH", "metrics.db")
LOG_FILE: str = _env("LOG_FILE", "server.log")
DB_HOST: str = _env("DB_HOST", "localhost")
DB_PORT: str = _env("DB_PORT", "5432")
DB_USER: str = _env("DB_USER", "admin")
DB_PASS: str = _env("DB_PASS", "password123")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ErrorEntry:
    """A parsed ERROR-level log line."""
    timestamp: str
    message: str


@dataclass
class UserEvent:
    """A parsed user login/logout event."""
    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """A parsed API call with latency measurement."""
    timestamp: str
    endpoint: str
    latency_ms: int


@dataclass
class WarningEntry:
    """A parsed WARN-level log line."""
    timestamp: str
    message: str


@dataclass
class LogData:
    """Aggregated results from log extraction."""
    errors: List[ErrorEntry] = field(default_factory=list)
    user_events: List[UserEvent] = field(default_factory=list)
    api_calls: List[ApiCall] = field(default_factory=list)
    warnings: List[WarningEntry] = field(default_factory=list)


@dataclass
class ReportData:
    """Transformed data ready for reporting."""
    error_counts: Dict[str, int] = field(default_factory=dict)
    api_latency: Dict[str, List[int]] = field(default_factory=dict)
    active_sessions: int = 0


# ---------------------------------------------------------------------------
# Regex patterns for log parsing
# ---------------------------------------------------------------------------

# General log-line format: "2024-01-01 12:00:00 LEVEL ..."
_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<payload>.+)$"
)

# User event: "User <id> <action>"
_USER_EVENT_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.+)$")

# API call: "API <endpoint> took <n>ms"
_API_CALL_RE = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?$")


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def extract(log_path: str) -> LogData:
    """Parse *log_path* and return structured :class:`LogData`.

    Returns an empty :class:`LogData` when the file does not exist.
    """
    data = LogData()
    path = Path(log_path)
    if not path.exists():
        return data

    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        match = _LOG_LINE_RE.match(line)
        if not match:
            continue

        ts = match.group("ts")
        level = match.group("level")
        payload = match.group("payload")

        if level == "ERROR":
            data.errors.append(ErrorEntry(timestamp=ts, message=payload))

        elif level == "WARN":
            data.warnings.append(WarningEntry(timestamp=ts, message=payload))

        elif level == "INFO":
            if payload.startswith("User"):
                user_match = _USER_EVENT_RE.match(payload)
                if user_match:
                    data.user_events.append(UserEvent(
                        timestamp=ts,
                        user_id=user_match.group("uid"),
                        action=user_match.group("action").strip(),
                    ))
            elif payload.startswith("API"):
                api_match = _API_CALL_RE.match(payload)
                if api_match:
                    ms_str = api_match.group("ms")
                    data.api_calls.append(ApiCall(
                        timestamp=ts,
                        endpoint=api_match.group("endpoint"),
                        latency_ms=int(ms_str) if ms_str else 0,
                    ))

    return data


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform(log_data: LogData) -> ReportData:
    """Aggregate extracted *log_data* into report-ready :class:`ReportData`."""
    # Error counts
    error_counts: Dict[str, int] = {}
    for err in log_data.errors:
        error_counts[err.message] = error_counts.get(err.message, 0) + 1

    # API latency aggregations
    api_latency: Dict[str, List[int]] = {}
    for call in log_data.api_calls:
        api_latency.setdefault(call.endpoint, []).append(call.latency_ms)

    # Active sessions – track login/logout, count still logged in
    sessions: set[str] = set()
    for event in log_data.user_events:
        if "logged in" in event.action:
            sessions.add(event.user_id)
        elif "logged out" in event.action:
            sessions.discard(event.user_id)

    return ReportData(
        error_counts=error_counts,
        api_latency=api_latency,
        active_sessions=len(sessions),
    )


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def _init_db(conn: sqlite3.Connection) -> None:
    """Create pipeline tables if they do not already exist."""
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def load(
    report_data: ReportData,
    db_path: str,
) -> None:
    """Persist *report_data* to SQLite and write ``report.html``.

    Uses parameterised queries throughout — no string interpolation in SQL.
    """
    now = datetime.datetime.now().isoformat()

    # --- Database ----------------------------------------------------------
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    conn = sqlite3.connect(db_path)
    _init_db(conn)
    cur = conn.cursor()

    for msg, count in report_data.error_counts.items():
        cur.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, times in report_data.api_latency.items():
        avg = sum(times) / len(times)
        cur.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg),
        )

    conn.commit()
    conn.close()

    # --- HTML report --------------------------------------------------------
    html = _render_html(report_data)
    Path("report.html").write_text(html, encoding="utf-8")

    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Report rendering (kept inside the Load step)
# ---------------------------------------------------------------------------

def _render_html(data: ReportData) -> str:
    """Build the HTML report string from *data*.

    All dynamic values are HTML-escaped to prevent injection in the report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in data.error_counts.items():
        lines.append(
            f"<li><b>{escape(msg)}</b>: {count} occurrences</li>"
        )

    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for endpoint, times in data.api_latency.items():
        avg = round(sum(times) / len(times), 1)
        lines.append(
            f"<tr><td>{escape(endpoint)}</td><td>{avg}</td></tr>"
        )

    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{data.active_sessions} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the extract-transform-load pipeline end to end."""
    # Bootstrap a sample log file when none exists (mirrors original behaviour)
    if not Path(LOG_FILE).exists():
        Path(LOG_FILE).write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n",
            encoding="utf-8",
        )

    raw = extract(LOG_FILE)
    report = transform(raw)
    load(report, DB_PATH)


if __name__ == "__main__":
    main()