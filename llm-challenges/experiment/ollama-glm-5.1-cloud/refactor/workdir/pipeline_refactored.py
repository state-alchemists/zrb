"""Server log processing pipeline: extract, transform, load.

Reads server logs, aggregates errors/API latency/sessions,
persists metrics to SQLite, and generates an HTML report.
"""

import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# --- Configuration -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Config:
    """Pipeline configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @classmethod
    def from_env(cls) -> "Config":
        """Build config from PIPELINE_* environment variables with defaults."""
        return cls(
            db_path=Path(os.getenv("PIPELINE_DB_PATH", "metrics.db")),
            log_file=Path(os.getenv("PIPELINE_LOG_FILE", "server.log")),
            db_host=os.getenv("PIPELINE_DB_HOST", "localhost"),
            db_port=int(os.getenv("PIPELINE_DB_PORT", "5432")),
            db_user=os.getenv("PIPELINE_DB_USER", "admin"),
            db_pass=os.getenv("PIPELINE_DB_PASS", "password123"),
        )


# --- Data models ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ErrorEntry:
    """A single ERROR-level log entry."""

    timestamp: str
    message: str


@dataclass(frozen=True, slots=True)
class UserEntry:
    """An INFO-level log entry about a user action."""

    timestamp: str
    user_id: str
    action: str


@dataclass(frozen=True, slots=True)
class ApiCallEntry:
    """An INFO-level log entry about an API call latency."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class WarnEntry:
    """A single WARN-level log entry."""

    timestamp: str
    message: str


@dataclass
class ReportData:
    """Aggregated data ready for reporting and persistence."""

    error_counts: dict[str, int] = field(default_factory=dict)
    api_latency: dict[str, list[int]] = field(default_factory=dict)
    active_sessions: int = 0


class ExtractedEntries(NamedTuple):
    """Typed container for parsed log entries."""

    errors: list[ErrorEntry]
    users: list[UserEntry]
    api_calls: list[ApiCallEntry]
    warnings: list[WarnEntry]


# --- Log-line patterns ------------------------------------------------------

_TS = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"

PATTERN_ERROR = re.compile(rf"^({_TS}) ERROR (.+)$")
PATTERN_USER = re.compile(rf"^({_TS}) INFO User (\S+) (.+)$")
PATTERN_API = re.compile(rf"^({_TS}) INFO API (\S+) took (\d+)ms$")
PATTERN_WARN = re.compile(rf"^({_TS}) WARN (.+)$")


# --- Extract ----------------------------------------------------------------


def extract_log_entries(log_file: Path) -> ExtractedEntries:
    """Parse a server log file into typed entry lists using regex matching."""
    errors: list[ErrorEntry] = []
    users: list[UserEntry] = []
    api_calls: list[ApiCallEntry] = []
    warnings: list[WarnEntry] = []

    if not log_file.exists():
        return ExtractedEntries(errors, users, api_calls, warnings)

    with log_file.open("r") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if match := PATTERN_API.match(line):
                api_calls.append(
                    ApiCallEntry(
                        timestamp=match.group(1),
                        endpoint=match.group(2),
                        duration_ms=int(match.group(3)),
                    )
                )
            elif match := PATTERN_USER.match(line):
                users.append(
                    UserEntry(
                        timestamp=match.group(1),
                        user_id=match.group(2),
                        action=match.group(3),
                    )
                )
            elif match := PATTERN_ERROR.match(line):
                errors.append(
                    ErrorEntry(
                        timestamp=match.group(1),
                        message=match.group(2),
                    )
                )
            elif match := PATTERN_WARN.match(line):
                warnings.append(
                    WarnEntry(
                        timestamp=match.group(1),
                        message=match.group(2),
                    )
                )

    return ExtractedEntries(errors, users, api_calls, warnings)


# --- Transform ---------------------------------------------------------------


def transform(
    errors: list[ErrorEntry],
    users: list[UserEntry],
    api_calls: list[ApiCallEntry],
) -> ReportData:
    """Aggregate raw entries into report-ready summaries."""
    error_counts: dict[str, int] = {}
    for err in errors:
        error_counts[err.message] = error_counts.get(err.message, 0) + 1

    api_latency: dict[str, list[int]] = {}
    for call in api_calls:
        api_latency.setdefault(call.endpoint, []).append(call.duration_ms)

    sessions: dict[str, str] = {}
    for user in users:
        if "logged in" in user.action:
            sessions[user.user_id] = user.timestamp
        elif "logged out" in user.action and user.user_id in sessions:
            sessions.pop(user.user_id)

    return ReportData(
        error_counts=error_counts,
        api_latency=api_latency,
        active_sessions=len(sessions),
    )


# --- Load --------------------------------------------------------------------


def _init_db(conn: sqlite3.Connection) -> None:
    """Create metrics tables if they do not already exist."""
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def load_to_db(db_path: Path, report_data: ReportData, now: datetime) -> None:
    """Persist aggregated metrics to SQLite using parameterized queries."""
    conn = sqlite3.connect(str(db_path))
    try:
        _init_db(conn)
        cur = conn.cursor()

        for msg, count in report_data.error_counts.items():
            cur.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (str(now), msg, count),
            )

        for endpoint, times in report_data.api_latency.items():
            avg = sum(times) / len(times)
            cur.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (str(now), endpoint, avg),
            )

        conn.commit()
    finally:
        conn.close()


def load_report(report_data: ReportData, output_path: Path) -> None:
    """Generate an HTML report from aggregated data."""
    avg_latency = {
        ep: round(sum(times) / len(times), 1)
        for ep, times in report_data.api_latency.items()
    }

    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err_msg, count in report_data.error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in avg_latency.items():
        lines.append(f"<tr><td>{ep}</td><td>{avg}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{report_data.active_sessions} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with output_path.open("w") as fh:
        fh.write("\n".join(lines))


# --- Orchestration -----------------------------------------------------------

DEFAULT_LOG_SAMPLE = (
    "2024-01-01 12:00:00 INFO User 42 logged in\n"
    "2024-01-01 12:05:00 ERROR Database timeout\n"
    "2024-01-01 12:05:05 ERROR Database timeout\n"
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
    "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
    "2024-01-01 12:10:00 INFO User 42 logged out\n"
)


def run_pipeline(config: Config | None = None) -> None:
    """Execute the full extract-transform-load pipeline."""
    if config is None:
        config = Config.from_env()

    if not config.log_file.exists():
        config.log_file.write_text(DEFAULT_LOG_SAMPLE)

    now = datetime.now()
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    entries = extract_log_entries(config.log_file)
    report_data = transform(entries.errors, entries.users, entries.api_calls)
    load_to_db(config.db_path, report_data, now)
    load_report(report_data, Path("report.html"))

    print(f"Job finished at {now}")


if __name__ == "__main__":
    run_pipeline()
