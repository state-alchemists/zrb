from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from etl_config import ETLConfig

# Regex patterns for parsing log lines.
# Expected formats (as currently produced by the script's dummy log generator):
#   2023-10-01 10:05:00 ERROR Connection failed
#   2023-10-01 10:00:00 INFO User 123 logged in
_LOG_ERROR_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+ERROR\s+(?P<msg>.*)\s*$"
)
_LOG_INFO_USER_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+INFO\s+User\s+(?P<user>\S+)\b.*\s*$"
)


@dataclass(frozen=True)
class ErrorEvent:
    timestamp: datetime
    message: str


@dataclass(frozen=True)
class UserActionEvent:
    timestamp: datetime
    user_id: str


Event = ErrorEvent | UserActionEvent


def extract_lines(config: ETLConfig) -> list[str]:
    """Extract raw log lines from the configured log file."""

    if not os.path.exists(config.log_file):
        return []
    with open(config.log_file, "r", encoding="utf-8") as f:
        return f.readlines()


def _parse_timestamp(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")


def parse_line(line: str) -> Optional[Event]:
    """Transform a raw log line into a strongly-typed event.

    Returns None for lines that do not match known formats.
    """

    m = _LOG_ERROR_RE.match(line)
    if m:
        ts = _parse_timestamp(m.group("date"), m.group("time"))
        return ErrorEvent(timestamp=ts, message=m.group("msg"))

    m = _LOG_INFO_USER_RE.match(line)
    if m:
        ts = _parse_timestamp(m.group("date"), m.group("time"))
        return UserActionEvent(timestamp=ts, user_id=m.group("user"))

    return None


def transform(lines: Iterable[str]) -> list[Event]:
    """Transform raw lines into structured events."""

    events: list[Event] = []
    for line in lines:
        event = parse_line(line)
        if event is not None:
            events.append(event)
    return events


def build_error_report(events: Iterable[Event]) -> dict[str, int]:
    """Aggregate error counts by message."""

    report: dict[str, int] = {}
    for event in events:
        if isinstance(event, ErrorEvent):
            report[event.message] = report.get(event.message, 0) + 1
    return report


def render_report_html(report: dict[str, int]) -> str:
    """Render report in the exact same HTML structure as the legacy script."""

    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"
    return html


def load(report_html: str, config: ETLConfig) -> None:
    """Load the produced report into the configured output file."""

    with open(config.report_file, "w", encoding="utf-8") as f:
        f.write(report_html)


def run_etl(config: ETLConfig) -> None:
    """Run ETL pipeline: Extract -> Transform -> Load."""

    lines = extract_lines(config)
    events = transform(lines)

    # "Simulate" database connection and insertion (legacy behavior).
    print(f"Connecting to {config.db_host} as {config.db_user}...")

    report = build_error_report(events)
    html = render_report_html(report)
    load(html, config)

    print("Done.")


def _create_dummy_log_if_missing(config: ETLConfig) -> None:
    if os.path.exists(config.log_file):
        return
    with open(config.log_file, "w", encoding="utf-8") as f:
        f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
        f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
        f.write("2023-10-01 10:10:00 ERROR Connection failed\n")


if __name__ == "__main__":
    config = ETLConfig()
    _create_dummy_log_if_missing(config)
    run_etl(config)
