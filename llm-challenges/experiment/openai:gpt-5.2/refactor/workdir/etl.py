from __future__ import annotations

import datetime as _dt
import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

# ----------------------------
# Configuration
# ----------------------------


@dataclass(frozen=True)
class ETLConfig:
    """Runtime configuration loaded from environment variables."""

    db_host: str
    db_user: str
    db_password: str
    log_file: str
    report_file: str


def load_config(environ: dict[str, str] | None = None) -> ETLConfig:
    env = os.environ if environ is None else environ
    return ETLConfig(
        db_host=env.get("ETL_DB_HOST", "localhost"),
        db_user=env.get("ETL_DB_USER", "admin"),
        db_password=env.get("ETL_DB_PASSWORD", ""),
        log_file=env.get("ETL_LOG_FILE", "server.log"),
        report_file=env.get("ETL_REPORT_FILE", "report.html"),
    )


# ----------------------------
# Extract
# ----------------------------


@dataclass(frozen=True)
class LogEvent:
    ts: str
    kind: str  # "ERR" | "USR"
    message: Optional[str] = None
    user_id: Optional[str] = None


# Matches common pattern: "YYYY-MM-DD HH:MM:SS LEVEL ..."
_LOG_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s*(?P<rest>.*)$"
)
_USER_RE = re.compile(r"\bUser\s+(?P<uid>\S+)")


def extract_events(lines: Iterable[str]) -> list[LogEvent]:
    events: list[LogEvent] = []
    for raw in lines:
        line = raw.strip("\n")
        if not line.strip():
            continue

        m = _LOG_RE.match(line.strip())
        if not m:
            # Ignore unparseable lines rather than crashing.
            continue

        ts = f"{m.group('date')} {m.group('time')}"
        level = m.group("level").upper()
        rest = (m.group("rest") or "").strip()

        if level == "ERROR":
            events.append(LogEvent(ts=ts, kind="ERR", message=rest))
            continue

        if level == "INFO":
            um = _USER_RE.search(rest)
            if um:
                events.append(LogEvent(ts=ts, kind="USR", user_id=um.group("uid")))

    return events


# ----------------------------
# Transform
# ----------------------------


def summarize_errors(events: Iterable[LogEvent]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for ev in events:
        if ev.kind != "ERR" or not ev.message:
            continue
        summary[ev.message] = summary.get(ev.message, 0) + 1
    return summary


# ----------------------------
# Load (simulated)
# ----------------------------


def load_to_db(*, config: ETLConfig, events: Iterable[LogEvent]) -> None:
    # Kept as a stub to preserve original behavior (no real insertion).
    print(f"Connecting to {config.db_host} as {config.db_user}...")
    _ = (events, config.db_password)  # avoid unused warnings; password intentionally not printed


# ----------------------------
# Report
# ----------------------------


def render_report_html(error_summary: dict[str, int]) -> str:
    # Keep the HTML structure identical to the original output.
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n</body>\n</html>"
    return out


def write_report(path: str, html: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ----------------------------
# Orchestration
# ----------------------------


def run_etl(config: ETLConfig) -> None:
    events: list[LogEvent] = []
    if os.path.exists(config.log_file):
        with open(config.log_file, "r", encoding="utf-8") as f:
            events = extract_events(f)

    load_to_db(config=config, events=events)

    error_summary = summarize_errors(events)
    report_html = render_report_html(error_summary)
    write_report(config.report_file, report_html)

    print(f"Job finished at {_dt.datetime.now()}")


def _ensure_dummy_log(path: str) -> None:
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


if __name__ == "__main__":
    cfg = load_config()
    _ensure_dummy_log(cfg.log_file)
    run_etl(cfg)
