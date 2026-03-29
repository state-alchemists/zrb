import datetime
import os
import re
from typing import List, Dict, Any

# Configuration from environment variables with sensible defaults for dev
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
REPORT_FILE = "report.html"

# Regex for parsing log lines robustly
# Matches "YYYY-MM-DD HH:MM:SS LEVEL Message" allowing for varying whitespace
LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
USER_PATTERN = re.compile(r"User\s+(\S+)")


def extract_data(file_path: str) -> List[Dict[str, Any]]:
    """Extracts and parses data from the specified log file."""
    data: List[Dict[str, Any]] = []
    if not os.path.exists(file_path):
        return data

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = LOG_PATTERN.match(line)
            if match:
                dt_str, level, message = match.groups()
                # Normalize date string spaces if there were multiple
                dt_str = re.sub(r"\s+", " ", dt_str)

                if level == "ERROR":
                    data.append({"d": dt_str, "t": "ERR", "m": message.strip()})
                elif level == "INFO" and "User" in message:
                    user_match = USER_PATTERN.search(message)
                    if user_match:
                        uid = user_match.group(1)
                        data.append({"d": dt_str, "t": "USR", "u": uid})
    return data


def transform_data(data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Transforms raw log data into an error count summary."""
    error_counts: Dict[str, int] = {}
    for item in data:
        if item.get("t") == "ERR":
            msg = item["m"]
            error_counts[msg] = error_counts.get(msg, 0) + 1
    return error_counts


def load_data(error_counts: Dict[str, int]) -> None:
    """Simulates loading data to a DB and generates the HTML report."""
    print(f"Connecting to {DB_HOST} as {DB_USER}...")
    # NOTE: DB insertion logic would go here

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n</body>\n</html>"

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(out)


def run_etl() -> None:
    """Executes the Extract, Transform, Load pipeline."""
    data = extract_data(LOG_FILE)
    error_counts = transform_data(data)
    load_data(error_counts)
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Setup dummy data if needed
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_etl()
