import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional


@dataclass(frozen=True, slots=True)
class LogConfig:
    """Configuration for the log processing pipeline."""

    db_path: Path = Path(os.getenv("DB_PATH", "metrics.db"))
    log_file: Path = Path(os.getenv("LOG_FILE", "server.log"))
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_user: str = os.getenv("DB_USER", "admin")
    db_pass: str = os.getenv("DB_PASS", "password123")


class ProcessedData(NamedTuple):
    """Container for processed log metrics."""

    error_summary: Dict[str, int]
    api_latencies: Dict[str, List[int]]
    active_sessions: int


def extract_logs(file_path: Path) -> List[str]:
    """Reads log lines from the specified file."""
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return f.readlines()


def transform_logs(lines: List[str]) -> ProcessedData:
    """Parses log lines and aggregates metrics."""
    # Regex patterns for parsing
    log_pattern = re.compile(
        r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<lvl>INFO|ERROR|WARN) (?P<msg>.*)$"
    )
    user_pattern = re.compile(r"User (?P<uid>\w+) (?P<action>logged (in|out))")
    api_pattern = re.compile(r"API (?P<endpoint>\S+)(?: took (?P<ms>\d+)ms)?")

    error_summary: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    sessions: Dict[str, str] = {}

    for line in lines:
        match = log_pattern.match(line.strip())
        if not match:
            continue

        dt = match.group("dt")
        lvl = match.group("lvl")
        msg = match.group("msg")

        if lvl == "ERROR":
            error_summary[msg] = error_summary.get(msg, 0) + 1

        elif lvl == "INFO":
            # Check for User activity
            user_match = user_pattern.search(msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if action == "logged in":
                    sessions[uid] = dt
                elif action == "logged out" and uid in sessions:
                    sessions.pop(uid)

            # Check for API call
            api_match = api_pattern.search(msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms") or 0)
                api_latencies.setdefault(endpoint, []).append(ms)

    return ProcessedData(
        error_summary=error_summary,
        api_latencies=api_latencies,
        active_sessions=len(sessions),
    )


def load_to_db(config: LogConfig, data: ProcessedData) -> None:
    """Persists metrics to the SQLite database using parameterized queries."""
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

        # Batch insert errors
        error_params = [
            (now, msg, count) for msg, count in data.error_summary.items()
        ]
        cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_params)

        # Batch insert API metrics
        api_params = []
        for endpoint, latencies in data.api_latencies.items():
            avg_ms = sum(latencies) / len(latencies) if latencies else 0.0
            api_params.append((now, endpoint, avg_ms))
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_params)

        conn.commit()


def generate_report(data: ProcessedData, output_path: str = "report.html") -> None:
    """Generates an HTML report from the processed metrics."""
    html_content = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in data.error_summary.items():
        html_content.append(f"<li><b>{msg}</b>: {count} occurrences</li>")

    html_content.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, latencies in data.api_latencies.items():
        avg_ms = sum(latencies) / len(latencies) if latencies else 0.0
        html_content.append(
            f"<tr><td>{endpoint}</td><td>{round(avg_ms, 1)}</td></tr>"
        )

    html_content.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{data.active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_content))


def run_pipeline() -> None:
    """Main pipeline execution function."""
    config = LogConfig()
    
    # Extract
    lines = extract_logs(config.log_file)
    
    # Transform
    data = transform_logs(lines)
    
    # Load
    load_to_db(config, data)
    generate_report(data)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Ensure log file exists for demonstration if not present
    if not Path("server.log").exists():
        with open("server.log", "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()
