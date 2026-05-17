import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Base class for parsed log entries."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class ApiMetric:
    """Represents an API latency measurement."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class UserSession:
    """Represents a user session event."""

    timestamp: str
    user_id: str
    action: str


class PipelineConfig:
    """Configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.db_path = os.environ.get("DB_PATH", "metrics.db")
        self.log_file = os.environ.get("LOG_FILE_PATH", "server.log")
        self.db_host = os.environ.get("DB_HOST", "localhost")
        self.db_port = os.environ.get("DB_PORT", "5432")
        self.db_user = os.environ.get("DB_USER", "admin")
        self.db_pass = os.environ.get("DB_PASS", "password123")


def parse_logs(log_path: Path) -> tuple[list[LogEntry], list[ApiMetric], dict[str, str]]:
    """Extracts data from the log file using regex."""
    errors: list[LogEntry] = []
    api_metrics: list[ApiMetric] = []
    sessions: dict[str, str] = {}

    log_pattern = re.compile(
        r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<lvl>\S+) (?P<msg>.*)$"
    )
    api_pattern = re.compile(r"API (?P<ep>\S+) took (?P<dur>\d+)ms")
    user_pattern = re.compile(r"User (?P<uid>\S+) (?P<act>.*)")

    if not log_path.exists():
        return errors, api_metrics, sessions

    with log_path.open("r") as f:
        for line in f:
            if match := log_pattern.match(line.strip()):
                dt, lvl, msg = match.groups()
                if lvl == "ERROR":
                    errors.append(LogEntry(dt, lvl, msg))
                elif lvl == "INFO":
                    _process_info_line(dt, msg, api_pattern, user_pattern, api_metrics, sessions)
    return errors, api_metrics, sessions


def _process_info_line(
    dt: str,
    msg: str,
    api_pattern: re.Pattern,
    user_pattern: re.Pattern,
    api_metrics: list[ApiMetric],
    sessions: dict[str, str],
) -> None:
    """Helper to process INFO level log lines."""
    if api_match := api_pattern.match(msg):
        api_metrics.append(
            ApiMetric(dt, api_match.group("ep"), int(api_match.group("dur")))
        )
    elif user_match := user_pattern.match(msg):
        uid = user_match.group("uid")
        act = user_match.group("act")
        if "logged in" in act:
            sessions[uid] = dt
        elif "logged out" in act:
            sessions.pop(uid, None)


def transform_metrics(
    errors: Iterable[LogEntry], api_metrics: Iterable[ApiMetric]
) -> tuple[dict[str, int], dict[str, float]]:
    """Transforms raw entries into summary statistics."""
    err_summary: dict[str, int] = {}
    for err in errors:
        err_summary[err.message] = err_summary.get(err.message, 0) + 1

    api_stats: dict[str, list[int]] = {}
    for metric in api_metrics:
        api_stats.setdefault(metric.endpoint, []).append(metric.duration_ms)

    avg_latencies = {
        ep: sum(durations) / len(durations) for ep, durations in api_stats.items()
    }
    return err_summary, avg_latencies


def load_to_db(
    config: PipelineConfig, err_summary: Mapping[str, int], avg_latencies: Mapping[str, float]
) -> None:
    """Saves metrics to SQLite using parameterized queries."""
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")
    now = datetime.datetime.now().isoformat()
    
    with sqlite3.connect(config.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        for msg, count in err_summary.items():
            cursor.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))

        for ep, avg in avg_latencies.items():
            cursor.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))


def generate_report(
    err_summary: Mapping[str, int], 
    avg_latencies: Mapping[str, float], 
    active_sessions_count: int
) -> None:
    """Generates the HTML report."""
    html = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    for msg, count in err_summary.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    
    html.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])
    for ep, avg in avg_latencies.items():
        html.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    
    html.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions_count} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    Path("report.html").write_text("\n".join(html))


def main() -> None:
    """Main execution flow."""
    config = PipelineConfig()
    log_path = Path(config.log_file)
    
    if not log_path.exists():
        log_path.write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )

    errors, api_metrics, sessions = parse_logs(log_path)
    err_summary, avg_latencies = transform_metrics(errors, api_metrics)
    
    load_to_db(config, err_summary, avg_latencies)
    generate_report(err_summary, avg_latencies, len(sessions))
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
