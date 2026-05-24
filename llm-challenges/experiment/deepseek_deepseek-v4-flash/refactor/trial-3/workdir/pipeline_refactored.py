"""Refactored server log pipeline: Extract -> Transform -> Load.

Reads server logs via regex, aggregates errors/API-latency/sessions,
writes results to SQLite (parameterized queries) and an HTML report.
"""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import Any


# ── Configuration (environment-driven) ─────────────────────────────────────

LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
DB_PATH: str = os.getenv("DB_PATH", "metrics.db")

# ── Log parsing patterns ──────────────────────────────────────────────────

_LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|WARN|INFO) "
    r"(?P<msg>.+)$"
)
_USER_RE = re.compile(r"^User (\S+) (.+)$")
_API_RE = re.compile(r"^API (\S+) took (\d+)ms$")


# ── Extract ───────────────────────────────────────────────────────────────


def _handle_info_line(
    msg: str,
    ts: str,
    events: list[dict[str, Any]],
    api_calls: list[dict[str, Any]],
    sessions: dict[str, str],
) -> None:
    """Parse an INFO-level message for user events or API calls."""
    usr = _USER_RE.match(msg)
    api = _API_RE.match(msg)
    if usr:
        uid: str = usr.group(1)
        action: str = usr.group(2)
        if "logged in" in action:
            sessions[uid] = ts
        elif "logged out" in action and uid in sessions:
            sessions.pop(uid, None)
        events.append(
            {"ts": ts, "type": "USR", "uid": uid, "action": action}
        )
    elif api:
        api_calls.append(
            {
                "ts": ts,
                "endpoint": api.group(1),
                "ms": int(api.group(2)),
            }
        )


def extract_logs(
    path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Read and parse server log into structured records.

    Returns (events, api_calls, active_sessions).
        events: all ERROR, WARN, and INFO-User entries.
        api_calls: API latency measurements (endpoint, ms).
        sessions: map of user_id -> login timestamp.
    """
    events: list[dict[str, Any]] = []
    api_calls: list[dict[str, Any]] = []
    sessions: dict[str, str] = {}

    if not os.path.exists(path):
        return events, api_calls, sessions

    with open(path) as f:
        for line in f:
            m = _LOG_RE.match(line)
            if not m:
                continue
            ts = m.group("ts")
            lvl = m.group("level")
            msg = m.group("msg")

            if lvl == "ERROR":
                events.append({"ts": ts, "type": "ERR", "msg": msg})
            elif lvl == "WARN":
                events.append({"ts": ts, "type": "WARN", "msg": msg})
            elif lvl == "INFO":
                _handle_info_line(msg, ts, events, api_calls, sessions)

    return events, api_calls, sessions


# ── Transform ──────────────────────────────────────────────────────────────


def transform_errors(events: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate error occurrences by message text.

    Returns dict mapping error message -> occurrence count.
    """
    counts: dict[str, int] = defaultdict(int)
    for ev in events:
        if ev["type"] == "ERR":
            counts[ev["msg"]] += 1
    return dict(counts)


def transform_api_stats(
    api_calls: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute average latency (ms) per API endpoint.

    Returns dict mapping endpoint -> average duration in ms.
    """
    totals: dict[str, list[int]] = defaultdict(list)
    for call in api_calls:
        totals[call["endpoint"]].append(call["ms"])
    return {
        ep: sum(times) / len(times) for ep, times in totals.items()
    }


# ── Load ───────────────────────────────────────────────────────────────────


def load_to_db(errors: dict[str, int], api_stats: dict[str, float]) -> None:
    """Write aggregated error counts and API latencies to SQLite.

    Uses parameterized queries to prevent SQL injection.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now: str = datetime.datetime.now().isoformat()
    for msg, count in errors.items():
        c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))
    for ep, avg in api_stats.items():
        c.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg)
        )

    conn.commit()
    conn.close()


def generate_report(
    errors: dict[str, int],
    api_stats: dict[str, float],
    session_count: int,
) -> str:
    """Build an HTML report with error summary, API latency, and sessions.

    Returns the full HTML string ready to write to disk.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in errors.items():
        lines.append(
            f"<li><b>{msg}</b>: {count} occurrences</li>"
        )
    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in api_stats.items():
        lines.append(
            f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>"
        )
    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{session_count} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines)


# ── Pipeline entry point ──────────────────────────────────────────────────


def main() -> None:
    """Run the full ETL pipeline: extract, transform, load, and report."""
    events, api_calls, sessions = extract_logs(LOG_FILE)
    errors = transform_errors(events)
    api_stats = transform_api_stats(api_calls)
    load_to_db(errors, api_stats)
    html = generate_report(errors, api_stats, len(sessions))
    with open("report.html", "w") as f:
        f.write(html)
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write(
                "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            )
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
