"""ETL pipeline for processing server logs and generating an HTML report.

This refactors the original `pipeline.py` into a maintainable and safer design:
- All configuration is provided via environment variables.
- SQL writes use parameterized queries.
- Parsing uses regex (more robust than ad-hoc string splitting).
- Logic is structured as Extract → Transform → Load.

The generated `report.html` contains the same information as before:
- Error summary
- API latency table (average per endpoint)
- Active session count
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# -----------------------------
# Config
# -----------------------------


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    db_path: Path
    log_file: Path
    report_path: Path

    # Kept only for backward compatibility with the original script's output.
    # (It printed a connection string containing host/port/user.)
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


def _get_env(name: str, *, default: Optional[str] = None) -> str:
    """Read an environment variable.

    Args:
        name: Environment variable name.
        default: Default value if unset.

    Returns:
        The environment variable value.

    Raises:
        RuntimeError: If the variable is not set and no default is provided.
    """

    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    """Load configuration from environment variables.

    Required:
        PIPELINE_DB_PATH
        PIPELINE_LOG_FILE

    Optional:
        PIPELINE_REPORT_PATH (default: report.html)
        PIPELINE_DB_HOST (default: localhost)
        PIPELINE_DB_PORT (default: 5432)
        PIPELINE_DB_USER (default: admin)
        PIPELINE_DB_PASS (default: password123)

    Notes:
        Although DB host/port/user/pass are not used by sqlite3, they were
        present in the original script and are preserved to meet the
        "all config via env vars" requirement without changing console output.
    """

    return Config(
        db_path=Path(_get_env("PIPELINE_DB_PATH")),
        log_file=Path(_get_env("PIPELINE_LOG_FILE")),
        report_path=Path(_get_env("PIPELINE_REPORT_PATH", default="report.html")),
        db_host=_get_env("PIPELINE_DB_HOST", default="localhost"),
        db_port=int(_get_env("PIPELINE_DB_PORT", default="5432")),
        db_user=_get_env("PIPELINE_DB_USER", default="admin"),
        db_pass=_get_env("PIPELINE_DB_PASS", default="password123"),
    )


# -----------------------------
# Extract (parse log)
# -----------------------------


# Example lines:
# 2024-01-01 12:00:00 INFO User 42 logged in
# 2024-01-01 12:05:00 ERROR Database timeout
# 2024-01-01 12:08:00 INFO API /users/profile took 250ms
# 2024-01-01 12:09:00 WARN Memory usage at 87%

_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<rest>.*)$"
)

_USER_RE = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
_API_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?\s*$"
)


@dataclass(frozen=True)
class ParsedLine:
    """A parsed log line."""

    dt: str  # kept as string to match original downstream behavior
    level: str
    rest: str


@dataclass(frozen=True)
class ApiCall:
    """A single API call timing extracted from the log."""

    dt: str
    endpoint: str
    ms: int


def read_log_lines(log_file: Path) -> Iterable[str]:
    """Yield log lines from a file if it exists."""

    if not log_file.exists():
        return
    with log_file.open("r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


def parse_log_line(line: str) -> Optional[ParsedLine]:
    """Parse a raw log line into structured fields using regex.

    Returns None if the line doesn't match the expected header format.
    """

    m = _LOG_LINE_RE.match(line)
    if not m:
        return None
    dt = f"{m.group('date')} {m.group('time')}"
    return ParsedLine(dt=dt, level=m.group("level"), rest=m.group("rest"))


def extract_events(lines: Iterable[str]) -> Tuple[List[str], List[ApiCall], Dict[str, str]]:
    """Extract errors, API calls, and active sessions from log lines.

    Returns:
        errors: list of error messages (one per occurrence)
        api_calls: list of ApiCall entries
        sessions: map of user_id -> login datetime string (currently active)
    """

    errors: List[str] = []
    api_calls: List[ApiCall] = []
    sessions: Dict[str, str] = {}

    for raw in lines:
        parsed = parse_log_line(raw)
        if parsed is None:
            continue

        if parsed.level == "ERROR":
            # Original code treated everything after the level as message
            errors.append(parsed.rest.strip())
            continue

        if parsed.level == "WARN":
            # Warns were collected in original d_list but not used in output.
            # We parse them (for completeness) but do not include them in outputs.
            continue

        if parsed.level == "INFO":
            user_m = _USER_RE.match(parsed.rest)
            if user_m:
                uid = user_m.group("uid")
                action = user_m.group("action").strip()
                if "logged in" in action:
                    sessions[uid] = parsed.dt
                elif "logged out" in action:
                    sessions.pop(uid, None)
                continue

            api_m = _API_RE.match(parsed.rest)
            if api_m:
                endpoint = api_m.group("endpoint")
                ms_str = api_m.group("ms")
                api_calls.append(
                    ApiCall(
                        dt=parsed.dt,
                        endpoint=endpoint,
                        ms=int(ms_str) if ms_str is not None else 0,
                    )
                )
                continue

    return errors, api_calls, sessions


# -----------------------------
# Transform
# -----------------------------


def summarize_errors(errors: Sequence[str]) -> Dict[str, int]:
    """Count occurrences of each error message."""

    counts: Dict[str, int] = {}
    for msg in errors:
        counts[msg] = counts.get(msg, 0) + 1
    return counts


def summarize_api_latency(api_calls: Sequence[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations (ms) by endpoint."""

    endpoint_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        endpoint_stats.setdefault(call.endpoint, []).append(call.ms)
    return endpoint_stats


def compute_avg_ms(times: Sequence[int]) -> float:
    """Compute average duration in milliseconds."""

    if not times:
        return 0.0
    return sum(times) / len(times)


# -----------------------------
# Load (DB + HTML report)
# -----------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create required tables if they don't exist."""

    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def write_metrics_to_db(
    conn: sqlite3.Connection,
    *,
    error_counts: Dict[str, int],
    endpoint_stats: Dict[str, List[int]],
    now: _dt.datetime,
) -> None:
    """Insert aggregated metrics into the database using parameterized queries."""

    c = conn.cursor()

    # Use ISO format for stable string representation.
    now_s = now.isoformat(sep=" ", timespec="seconds")

    for msg, count in error_counts.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_s, msg, count),
        )

    for ep, times in endpoint_stats.items():
        avg = compute_avg_ms(times)
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_s, ep, avg),
        )


def render_report_html(
    *,
    error_counts: Dict[str, int],
    endpoint_stats: Dict[str, List[int]],
    active_sessions: int,
) -> str:
    """Render the HTML report.

    The structure and contents match the original script's output.
    """

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"

    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += (
            "<li><b>" + err_msg + "</b>: " + str(count) + " occurrences</li>\n"
        )
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in endpoint_stats.items():
        avg = compute_avg_ms(times)
        out += "<tr><td>" + ep + "</td><td>" + str(round(avg, 1)) + "</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += "<p>" + str(active_sessions) + " user(s) currently active</p>\n"

    out += "</body>\n</html>"
    return out


def write_report(report_path: Path, html: str) -> None:
    """Write the report HTML to disk."""

    report_path.write_text(html, encoding="utf-8")


# -----------------------------
# Orchestration
# -----------------------------


def run_pipeline(config: Config) -> None:
    """Run the Extract → Transform → Load pipeline."""

    # EXTRACT
    errors, api_calls, sessions = extract_events(read_log_lines(config.log_file))

    # TRANSFORM
    error_counts = summarize_errors(errors)
    endpoint_stats = summarize_api_latency(api_calls)

    # LOAD
    print(
        "Connecting to "
        + config.db_host
        + ":"
        + str(config.db_port)
        + " as "
        + config.db_user
        + "..."
    )

    now = _dt.datetime.now()
    conn = sqlite3.connect(str(config.db_path))
    try:
        init_db(conn)
        write_metrics_to_db(
            conn,
            error_counts=error_counts,
            endpoint_stats=endpoint_stats,
            now=now,
        )
        conn.commit()
    finally:
        conn.close()

    html = render_report_html(
        error_counts=error_counts,
        endpoint_stats=endpoint_stats,
        active_sessions=len(sessions),
    )
    write_report(config.report_path, html)

    print("Job finished at " + str(now))


def _maybe_create_sample_log(log_file: Path) -> None:
    """Create a sample log file (only if it doesn't exist).

    This preserves the original script's behavior for local demos.
    """

    if log_file.exists():
        return

    log_file.write_text(
        """2024-01-01 12:00:00 INFO User 42 logged in
2024-01-01 12:05:00 ERROR Database timeout
2024-01-01 12:05:05 ERROR Database timeout
2024-01-01 12:08:00 INFO API /users/profile took 250ms
2024-01-01 12:09:00 WARN Memory usage at 87%
2024-01-01 12:10:00 INFO User 42 logged out
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    cfg = load_config()
    _maybe_create_sample_log(cfg.log_file)
    run_pipeline(cfg)
