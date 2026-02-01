import re
import os
from typing import List, Dict, TypedDict


# Configuration (separated from code)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "admin")
LOG_FILE = os.getenv("LOG_FILE", "server.log")


class LogEntry(TypedDict):
    date: str
    level: str
    message: str


def extract() -> List[LogEntry]:
    entries: List[LogEntry] = []
    if not os.path.exists(LOG_FILE):
        return entries

    with open(LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            match = re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (INFO|ERROR) (.+)$', line)
            if match:
                date = line[:19]
                level = match.group(1)
                message = match.group(2)
                entries.append({
                    "date": date,
                    "level": level,
                    "message": message
                })
    return entries


def transform(entries: List[LogEntry]) -> Dict[str, int]:
    error_counts: Dict[str, int] = {}
    for entry in entries:
        if entry["level"] == "ERROR":
            msg = entry["message"]
            error_counts[msg] = error_counts.get(msg, 0) + 1
    return error_counts


def load(report: Dict[str, int]) -> None:
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    html = "<html><body><h1>Report</h1><ul>"
    for msg, count in report.items():
        html += f"<li>{msg}: {count}</li>"
    html += "</ul></body></html>"

    with open("report.html", "w") as f:
        f.write(html)
    print("Done.")


def main():
    # Create dummy log if needed (testing setup)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    entries = extract()
    report = transform(entries)
    load(report)


if __name__ == "__main__":
    main()