from __future__ import annotations

import datetime as dt
import html
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

LOG_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+(?P<message>.*\S)?\s*$"
)
USER_PATTERN = re.compile(r"\bUser\s+(?P<user_id>\S+)")
DEFAULT_LOG_CONTENT = """2024-01-01 12:00:00 INFO User 42 logged in
2024-01-01 12:05:00 ERROR Database timeout
2024-01-01 12:05:05 ERROR Database timeout
2024-01-01 12:10:00 INFO User 42 logged out
"""


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_user: str
    db_password: str
    log_file: Path
    report_file: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_host=os.getenv("ETL_DB_HOST", "localhost"),
            db_user=os.getenv("ETL_DB_USER", "admin"),
            db_password=os.getenv("ETL_DB_PASSWORD", "password123"),
            log_file=Path(os.getenv("ETL_LOG_FILE", "server.log")),
            report_file=Path(os.getenv("ETL_REPORT_FILE", "report.html")),
        )


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class UserActivity:
    timestamp: str
    user_id: str


ExtractedRecord = LogEntry | UserActivity


def ensure_sample_log(log_file: Path) -> None:
    if not log_file.exists():
        log_file.write_text(DEFAULT_LOG_CONTENT, encoding="utf-8")


def extract_records(log_file: Path) -> list[ExtractedRecord]:
    if not log_file.exists():
        return []

    records: list[ExtractedRecord] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            entry = parse_log_line(raw_line)
            if entry is not None:
                records.extend(transform_entry(entry))
    return records


def parse_log_line(raw_line: str) -> LogEntry | None:
    match = LOG_PATTERN.match(raw_line.strip())
    if match is None:
        return None

    timestamp = f"{match.group('date')} {match.group('time')}"
    message = (match.group("message") or "").strip()
    return LogEntry(timestamp=timestamp, level=match.group("level"), message=message)


def transform_entry(entry: LogEntry) -> Iterator[ExtractedRecord]:
    if entry.level == "ERROR":
        yield entry
        return

    if entry.level == "INFO":
        user_match = USER_PATTERN.search(entry.message)
        if user_match is not None:
            yield UserActivity(timestamp=entry.timestamp, user_id=user_match.group("user_id"))


def load_records(records: Iterable[ExtractedRecord], settings: Settings) -> None:
    print(f"Connecting to {settings.db_host} as {settings.db_user}...")
    _ = settings.db_password
    for _record in records:
        pass


def summarize_errors(records: Iterable[ExtractedRecord]) -> Counter[str]:
    return Counter(
        record.message
        for record in records
        if isinstance(record, LogEntry) and record.level == "ERROR"
    )


def render_report(error_summary: Counter[str]) -> str:
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err_msg, count in error_summary.items():
        safe_message = html.escape(err_msg)
        lines.append(f"<li><b>{safe_message}</b>: {count} occurrences</li>")
    lines.extend(["</ul>", "</body>", "</html>"])
    return "\n".join(lines)


def write_report(report_file: Path, report_html: str) -> None:
    report_file.write_text(report_html, encoding="utf-8")


def run() -> None:
    settings = Settings.from_env()
    ensure_sample_log(settings.log_file)
    records = extract_records(settings.log_file)
    load_records(records, settings)
    error_summary = summarize_errors(records)
    write_report(settings.report_file, render_report(error_summary))
    print(f"Job finished at {dt.datetime.now()}")


if __name__ == "__main__":
    run()
