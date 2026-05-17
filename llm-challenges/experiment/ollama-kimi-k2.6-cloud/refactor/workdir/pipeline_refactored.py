"""ETL pipeline that processes server logs and produces a SQLite database + HTML report."""

import datetime
import html
import os
import re
import sqlite3
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_LOG_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<rest>.*)$"
)
_USER_RE = re.compile(r"^User (?P<uid>\S+) (?P<action>.+)$")
_API_RE = re.compile(r"^API (?P<endpoint>\S+) took (?P<dur>\d+)ms$")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LogRecord:
    """A generic log line parsed from the server log."""

    dt: str
    level: str
    message: str


@dataclass(frozen=True)
class UserEvent:
    """A user login/logout event."""

    dt: str
    user_id: str
    action: str


@dataclass(frozen=True)
class ApiEvent:
    """An API call event with latency."""

    dt: str
    endpoint: str
    ms: int


Event = LogRecord | UserEvent | ApiEvent


@dataclass
class ParsedData:
    """Container for all data extracted from the log file."""

    events: list[Event] = field(default_factory=list)


@dataclass
class ReportData:
    """Aggregated report data ready for load / render."""

    error_counts: dict[str, int]
    api_averages: dict[str, float]
    active_sessions: int
    generated_at: str


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Config:
    """Pipeline configuration read from environment variables."""

    db_path: str
    log_file: str
    report_path: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from the process environment."""
        return cls(
            db_path=_env("DB_PATH", "metrics.db"),
            log_file=_env("LOG_FILE", "server.log"),
            report_path=_env("REPORT_PATH", "report.html"),
            db_host=_env("DB_HOST", "localhost"),
            db_port=int(_env("DB_PORT", "5432")),
            db_user=_env("DB_USER", "admin"),
            db_pass=_env("DB_PASS", "password123"),
        )


def _env(key: str, default: str) -> str:
    """Return the environment variable *key* or its *default*."""
    return os.getenv(key, default)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------
def extract(log_path: str) -> ParsedData:
    """Parse *log_path* and return structured events.

    If the file does not exist an empty :class:`ParsedData` is returned.
    """
    data = ParsedData()
    if not os.path.exists(log_path):
        return data

    with open(log_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            event = _parse_line(line)
            if event is not None:
                data.events.append(event)

    return data


def _parse_line(line: str) -> Event | None:
    """Convert a single log *line* into a typed event."""
    m = _LOG_RE.match(line)
    if not m:
        return None

    dt = m.group("dt")
    level = m.group("level")
    rest = m.group("rest")

    if level == "ERROR":
        return LogRecord(dt, "ERROR", rest)

    if level == "WARN":
        return LogRecord(dt, "WARN", rest)

    if level == "INFO":
        um = _USER_RE.match(rest)
        if um:
            return UserEvent(dt, um.group("uid"), um.group("action"))

        am = _API_RE.match(rest)
        if am:
            return ApiEvent(dt, am.group("endpoint"), int(am.group("dur")))

    return None


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------
def transform(data: ParsedData) -> ReportData:
    """Aggregate extracted *data* into a :class:`ReportData`."""
    error_counts: dict[str, int] = {}
    api_times: dict[str, list[int]] = {}
    sessions: dict[str, str] = {}

    for ev in data.events:
        if isinstance(ev, LogRecord) and ev.level == "ERROR":
            error_counts[ev.message] = error_counts.get(ev.message, 0) + 1
        elif isinstance(ev, ApiEvent):
            api_times.setdefault(ev.endpoint, []).append(ev.ms)
        elif isinstance(ev, UserEvent):
            if "logged in" in ev.action:
                sessions[ev.user_id] = ev.dt
            elif "logged out" in ev.action and ev.user_id in sessions:
                sessions.pop(ev.user_id)

    api_averages = {
        ep: sum(times) / len(times) for ep, times in api_times.items()
    }

    return ReportData(
        error_counts=error_counts,
        api_averages=api_averages,
        active_sessions=len(sessions),
        generated_at=str(datetime.datetime.now()),
    )


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load(report: ReportData, db_path: str) -> None:
    """Persist *report* aggregates into the SQLite database at *db_path*."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = str(datetime.datetime.now())

    for msg, count in report.error_counts.items():
        cur.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for ep, avg in report.api_averages.items():
        cur.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, ep, avg),
        )

    conn.commit()
    conn.close()


def render_html(report: ReportData, output_path: str) -> None:
    """Write an HTML summary of *report* to *output_path*."""
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in report.error_counts.items():
        safe_msg = html.escape(msg)
        lines.append(f"<li><b>{safe_msg}</b>: {count} occurrences</li>")

    lines.extend(
        [
            "</ul>",
            "<h2>API Latency</h2>",
            "<table border='1'>",
            "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
        ]
    )

    for ep, avg in report.api_averages.items():
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend(
        [
            "</table>",
            "<h2>Active Sessions</h2>",
            f"<p>{report.active_sessions} user(s) currently active</p>",
            "</body>",
            "</html>",
        ]
    )

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_pipeline(config: Config) -> None:
    """Execute the full ETL pipeline using *config*."""
    print(
        f"Connecting to {config.db_host}:{config.db_port} "
        f"as {config.db_user}..."
    )

    data = extract(config.log_file)
    report = transform(data)
    load(report, config.db_path)
    render_html(report, config.report_path)

    print(f"Job finished at {report.generated_at}")


def _ensure_sample_log(log_path: str) -> None:
    """Create a sample log file at *log_path* if it does not exist."""
    if os.path.exists(log_path):
        return

    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sample_lines) + "\n")


if __name__ == "__main__":
    cfg = Config.from_env()
    _ensure_sample_log(cfg.log_file)
    run_pipeline(cfg)
