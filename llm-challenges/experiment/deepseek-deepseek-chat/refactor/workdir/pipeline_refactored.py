"""Pipeline: Extract server logs → Transform metrics → Load report.

Environment variables:
    DB_PATH        — SQLite database file (default: metrics.db)
    LOG_FILE       — path to server log file (default: server.log)
    DB_HOST        — host label for status message (default: localhost)
    DB_PORT        — port label for status message (default: 5432)
    DB_USER        — user label for status message (default: admin)
    DB_PASS        — unused, kept for backward compat (default: password123)
"""

import datetime
import html
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    """Immutable configuration loaded from environment variables."""

    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "metrics.db"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "server.log"))
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: str = field(default_factory=lambda: os.getenv("DB_PORT", "5432"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "admin"))


# ---------------------------------------------------------------------------
# Extract — log line records
# ---------------------------------------------------------------------------

# Regex patterns for each log line type.
# Common format: <date> <time> <LEVEL> <rest...>
_RE_ERROR = re.compile(
    r"^(?P<dt>\S+ \S+)\s+ERROR\s+(?P<message>.+)$"
)
_RE_USER = re.compile(
    r"^(?P<dt>\S+ \S+)\s+INFO\s+User\s+(?P<uid>\S+)\s+(?P<action>.+)$"
)
_RE_API = re.compile(
    r"^(?P<dt>\S+ \S+)\s+INFO\s+API\s+(?P<endpoint>\S+).*?took\s+(?P<ms>\d+)ms"
)
_RE_WARN = re.compile(
    r"^(?P<dt>\S+ \S+)\s+WARN\s+(?P<message>.+)$"
)


@dataclass
class LogEntry:
    """A single parsed log entry."""

    timestamp: str
    kind: str  # ERR | WARN | USR
    message: str = ""
    user_id: str = ""
    action: str = ""
    endpoint: str = ""
    latency_ms: int = 0


def parse_log_line(line: str) -> LogEntry | None:
    """Parse one log line into a typed record, or None if unparseable."""
    m = _RE_ERROR.match(line)
    if m:
        return LogEntry(timestamp=m.group("dt"), kind="ERR", message=m.group("message"))

    m = _RE_USER.match(line)
    if m:
        return LogEntry(
            timestamp=m.group("dt"),
            kind="USR",
            user_id=m.group("uid"),
            action=m.group("action"),
        )

    m = _RE_API.match(line)
    if m:
        return LogEntry(
            timestamp=m.group("dt"),
            kind="API",
            endpoint=m.group("endpoint"),
            latency_ms=int(m.group("ms")),
        )

    m = _RE_WARN.match(line)
    if m:
        return LogEntry(timestamp=m.group("dt"), kind="WARN", message=m.group("message"))

    return None


def extract_logs(log_path: str) -> list[LogEntry]:
    """Read a log file and return all parseable entries."""
    path = Path(log_path)
    if not path.exists():
        return []

    entries: list[LogEntry] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is not None:
                entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Transform — aggregate into summary structures
# ---------------------------------------------------------------------------

@dataclass
class SessionTracker:
    """Tracks user login/logout state over a sequence of log entries."""

    active: dict[str, str] = field(default_factory=dict)

    def apply(self, entry: LogEntry) -> None:
        if entry.action and "logged in" in entry.action:
            self.active[entry.user_id] = entry.timestamp
        elif entry.action and "logged out" in entry.action:
            self.active.pop(entry.user_id, None)


@dataclass
class AggregatedMetrics:
    """Ready-to-load summary data."""

    error_counts: dict[str, int] = field(default_factory=dict)
    api_latencies: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    active_sessions: int = 0


def transform(entries: list[LogEntry]) -> AggregatedMetrics:
    """Aggregate log entries into error counts, API latencies, and session count."""
    metrics = AggregatedMetrics()
    sessions = SessionTracker()

    for entry in entries:
        if entry.kind == "ERR":
            metrics.error_counts[entry.message] = metrics.error_counts.get(entry.message, 0) + 1
        elif entry.kind == "API":
            metrics.api_latencies[entry.endpoint].append(entry.latency_ms)
        elif entry.kind == "USR":
            sessions.apply(entry)

    metrics.active_sessions = len(sessions.active)
    return metrics


# ---------------------------------------------------------------------------
# Load — database
# ---------------------------------------------------------------------------

_DDL = [
    "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)",
    "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)",
]


def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    for ddl in _DDL:
        conn.execute(ddl)


def _store_errors(conn: sqlite3.Connection, error_counts: dict[str, int]) -> None:
    """Insert aggregated error counts using parameterized queries."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, cnt) for msg, cnt in error_counts.items()],
    )


def _store_api_metrics(conn: sqlite3.Connection, api_latencies: dict[str, list[int]]) -> None:
    """Insert average API latency per endpoint using parameterized queries."""
    now = datetime.datetime.now().isoformat()
    rows = [
        (now, ep, sum(times) / len(times))
        for ep, times in api_latencies.items()
    ]
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        rows,
    )


def load_to_db(cfg: Config, metrics: AggregatedMetrics) -> None:
    """Write aggregated metrics into the SQLite database."""
    conn = sqlite3.connect(cfg.db_path)
    try:
        _init_db(conn)
        _store_errors(conn, metrics.error_counts)
        _store_api_metrics(conn, metrics.api_latencies)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Load — HTML report
# ---------------------------------------------------------------------------

_TEMPLATE = """\
<html>
<head><title>System Report</title></head>
<body>
<h1>Error Summary</h1>
<ul>
{errors}
</ul>
<h2>API Latency</h2>
<table border="1">
<tr><th>Endpoint</th><th>Avg (ms)</th></tr>
{api_rows}
</table>
<h2>Active Sessions</h2>
<p>{session_count} user(s) currently active</p>
</body>
</html>"""


def _build_error_items(error_counts: dict[str, int]) -> str:
    """Render error summary as HTML list items."""
    lines = []
    for msg, cnt in sorted(error_counts.items(), key=lambda x: -x[1]):
        safe_msg = html.escape(msg)
        lines.append(f"<li><b>{safe_msg}</b>: {cnt} occurrences</li>\n")
    return "".join(lines)


def _build_api_rows(api_latencies: dict[str, list[int]]) -> str:
    """Render API latency table rows."""
    lines = []
    for ep, times in sorted(api_latencies.items()):
        avg = sum(times) / len(times)
        safe_ep = html.escape(ep)
        lines.append(f"<tr><td>{safe_ep}</td><td>{avg:.1f}</td></tr>\n")
    return "".join(lines)


def generate_report(metrics: AggregatedMetrics, output_path: str = "report.html") -> None:
    """Write an HTML report summarising error counts, API latency, and sessions."""
    html_content = _TEMPLATE.format(
        errors=_build_error_items(metrics.error_counts),
        api_rows=_build_api_rows(metrics.api_latencies),
        session_count=metrics.active_sessions,
    )
    Path(output_path).write_text(html_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _print_status(cfg: Config) -> None:
    """Print a connection-status message (backward compat)."""
    print(f"Connecting to {cfg.db_host}:{cfg.db_port} as {cfg.db_user}...")


def _generate_sample_log(log_path: str) -> None:
    """Create a sample log file with representative entries."""
    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]
    Path(log_path).write_text("".join(lines), encoding="utf-8")


def run_pipeline(cfg: Config | None = None) -> None:
    """Execute the full Extract → Transform → Load pipeline."""
    cfg = cfg or Config()

    _print_status(cfg)

    entries = extract_logs(cfg.log_file)
    metrics = transform(entries)
    load_to_db(cfg, metrics)
    generate_report(metrics)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    cfg = Config()
    if not os.path.exists(cfg.log_file):
        _generate_sample_log(cfg.log_file)
    run_pipeline(cfg)
