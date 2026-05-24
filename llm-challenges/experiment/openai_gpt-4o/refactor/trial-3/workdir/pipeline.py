import datetime
import os
import re
import sqlite3
from typing import List, Dict, Tuple

# Configuration from environment variables
def get_env_variable(var_name: str, default: str) -> str:
    """Retrieve environment variable or return default."""
    return os.getenv(var_name, default)

DB_PATH = get_env_variable('DB_PATH', 'metrics.db')
LOG_FILE = get_env_variable('LOG_FILE', 'server.log')
DB_HOST = get_env_variable('DB_HOST', 'localhost')
DB_PORT = int(get_env_variable('DB_PORT', '5432'))
DB_USER = get_env_variable('DB_USER', 'admin')
DB_PASS = get_env_variable('DB_PASS', 'password123')


def extract_logs(file_path: str) -> Tuple[List[Dict], List[Dict], Dict]:
    """Extracts error, user activity, and API call logs."""
    d_list = []
    sessions = {}
    api_calls = []
    log_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\S+) (.+)$"
    )

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                match = log_pattern.match(line)
                if match:
                    dt, lvl, msg = match.groups()
                    if lvl == "ERROR":
                        d_list.append({"d": dt, "t": "ERR", "m": msg})

                    elif lvl == "INFO" and "User" in msg:
                        uid_action = re.search(r"User (\d+) (.+)", msg)
                        if uid_action:
                            uid, action = uid_action.groups()
                            if "logged in" in action:
                                sessions[uid] = dt
                            elif "logged out" in action and uid in sessions:
                                sessions.pop(uid)
                            d_list.append({"d": dt, "t": "USR", "u": uid, "a": action})

                    elif lvl == "INFO" and "API" in msg:
                        api_action = re.search(r"API (\S+) took (\d+)ms", msg)
                        if api_action:
                            endpoint, dur = api_action.groups()
                            api_calls.append({"d": dt, "endpoint": endpoint, "ms": int(dur)})

                    elif lvl == "WARN":
                        d_list.append({"d": dt, "t": "WARN", "m": msg})

    return d_list, api_calls, sessions


def transform_data(d_list: List[Dict], api_calls: List[Dict]) -> Tuple[Dict[str, int], Dict[str, float]]:
    """Transforms extracted data into summary metrics for database insertion."""
    error_summary = {}
    for item in d_list:
        if item["t"] == "ERR":
            msg = item["m"]
            error_summary[msg] = error_summary.get(msg, 0) + 1

    api_summary = {}
    for call in api_calls:
        ep = call["endpoint"]
        api_summary.setdefault(ep, []).append(call["ms"])

    for ep, times in api_summary.items():
        api_summary[ep] = sum(times) / len(times)

    return error_summary, api_summary


def load_data_to_db(error_summary: Dict[str, int], api_summary: Dict[str, float], sessions: Dict) -> None:
    """Loads transformed data into the database and generates the HTML report."""
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    for msg, count in error_summary.items():
        cursor.execute("INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                       (datetime.datetime.now(), msg, count))

    for ep, avg in api_summary.items():
        cursor.execute("INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                       (datetime.datetime.now(), ep, avg))

    conn.commit()
    conn.close()

    generate_report_html(error_summary, api_summary, sessions)


def generate_report_html(error_summary: Dict[str, int], api_summary: Dict[str, float], sessions: Dict) -> None:
    """Generates an HTML report of the data"""
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_summary.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

    print(f"Job finished at {datetime.datetime.now()}")



if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    proc_data()
