from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Sequence, TypedDict

LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>INFO|ERROR)\s+(?P<message>.*)$"
)
USER_ACTION_RE = re.compile(r"\bUser\s+(?P<user_id>\S+)\b")


@dataclass(frozen=True)
class Config:
    """Configuration separated from ETL logic."""

    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    report_file: str = "report.html"

    @staticmethod
    def from_env(env: Optional[Dict[str, str]] = None) -> "Config":
        env = env or os.environ
        return Config(
            db_host=env.get("DB_HOST", "localhost"),
            db_user=env.get("DB_USER", "admin"),
            log_file=env.get("LOG_FILE", "server.log"),
            report_file=env.get("REPORT_FILE", "report.html"),
        )


class ErrorEvent(TypedDict):
    type: Literal["ERROR"]
    date: str
    msg: str


class UserActionEvent(TypedDict):
    type: Literal["USER_ACTION"]
    date: str
    user: str


Event = ErrorEvent | UserActionEvent


# ----------------------------
# ETL: Extract
# ----------------------------


def extract_lines(log_file: str) -> List[str]:
    if not os.path.exists(log_file):
        return []
    with open(log_file, "r") as f:
        return f.readlines()


# ----------------------------
# ETL: Transform
# ----------------------------


def parse_event(line: str) -> Optional[Event]:
    """Parse a single log line into a structured event.

    Uses regex to avoid fragile split-based parsing.
    """

    match = LOG_LINE_RE.match(line.rstrip("\n"))
    if not match:
        return None

    date_time = f"{match.group('date')} {match.group('time')}"
    level = match.group("level")
    message = match.group("message").strip()

    if level == "ERROR":
        return {"type": "ERROR", "date": date_time, "msg": message}

    if level == "INFO":
        user_match = USER_ACTION_RE.search(message)
        if not user_match:
            return None
        return {
            "type": "USER_ACTION",
            "date": date_time,
            "user": user_match.group("user_id"),
        }

    return None


def transform(lines: Sequence[str]) -> List[Event]:
    events: List[Event] = []
    for line in lines:
        event = parse_event(line)
        if event is not None:
            events.append(event)
    return events


def build_report(events: Iterable[Event]) -> Dict[str, int]:
    report: Dict[str, int] = {}
    for item in events:
        if item["type"] == "ERROR":
            msg = item["msg"]
            report[msg] = report.get(msg, 0) + 1
    return report


def render_report_html(report: Dict[str, int]) -> str:
    # Keep output identical to the original implementation.
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"
    return html


# ----------------------------
# ETL: Load
# ----------------------------


def load_report(report_html: str, report_file: str) -> None:
    with open(report_file, "w") as f:
        f.write(report_html)


def simulate_db_connection(db_host: str, db_user: str) -> None:
    # Preserve original side effect/console output.
    print(f"Connecting to {db_host} as {db_user}...")


def run_etl(config: Config) -> None:
    lines = extract_lines(config.log_file)
    events = transform(lines)

    simulate_db_connection(config.db_host, config.db_user)

    report = build_report(events)
    html = render_report_html(report)
    load_report(html, config.report_file)

    print("Done.")


def ensure_dummy_log_exists(log_file: str) -> None:
    """Create the same dummy log file as before for local testing."""

    if os.path.exists(log_file):
        return
    with open(log_file, "w") as f:
        f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
        f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
        f.write("2023-10-01 10:10:00 ERROR Connection failed\n")


if __name__ == "__main__":
    cfg = Config.from_env()
    ensure_dummy_log_exists(cfg.log_file)
    run_etl(cfg)
