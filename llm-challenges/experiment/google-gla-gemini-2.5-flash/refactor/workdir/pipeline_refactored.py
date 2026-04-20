import datetime
import os
import sqlite3
import re
from typing import List, Dict, Optional

def parse_log_line(line: str) -> Optional[Dict]:
    """Parses a single log line using regex and returns a dictionary of extracted data."""
    # Regex for ERROR, INFO (User), INFO (API), WARN messages
    error_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.*)$")
    user_info_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\d+) (.*)$")
    api_info_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (\S+) took (\d+)ms$")
    warn_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.*)$")

    if match := error_pattern.match(line):
        return {"d": match.group(1), "t": "ERR", "m": match.group(2).strip()}
    elif match := user_info_pattern.match(line):
        return {"d": match.group(1), "t": "USR", "u": match.group(2), "a": match.group(3).strip()}
    elif match := api_info_pattern.match(line):
        return {"d": match.group(1), "endpoint": match.group(2), "ms": int(match.group(3))}
    elif match := warn_pattern.match(line):
        return {"d": match.group(1), "t": "WARN", "m": match.group(2).strip()}
    return None

def load_logs(log_file_path: str) -> List[str]:
    """Loads log lines from the specified file."""
    if not os.path.exists(log_file_path):
        return []
    with open(log_file_path, "r") as f:
        return f.readlines()

def process_raw_logs(log_lines: List[str]) -> tuple[List[Dict], Dict[str, str], List[Dict]]:
    """Processes raw log lines, parsing them and categorizing them into different lists.
    Returns a tuple containing (d_list, sessions, api_calls)."""
    d_list = []
    sessions = {}
    api_calls = []

    for line in log_lines:
        if parsed_line := parse_log_line(line):
            if parsed_line.get("t") == "ERR":
                d_list.append(parsed_line)
            elif parsed_line.get("t") == "USR":
                uid = parsed_line["u"]
                action = parsed_line["a"]
                if "logged in" in action:
                    sessions[uid] = parsed_line["d"]
                elif "logged out" in action and uid in sessions:
                    sessions.pop(uid)
                d_list.append(parsed_line)
            elif parsed_line.get("endpoint"):  # API call
                api_calls.append(parsed_line)
            elif parsed_line.get("t") == "WARN":
                d_list.append(parsed_line)
    return d_list, sessions, api_calls

def proc_data():
    db_path = os.getenv("DB_PATH", "metrics.db")
    log_file = os.getenv("LOG_FILE", "server.log")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", 5432))
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")

    log_lines = load_logs(log_file)
    d_list, sessions, api_calls = process_raw_logs(log_lines)

    print(f"d_list: {d_list}") # Debug print
    print(f"api_calls: {api_calls}") # Debug print

    print("Connecting to " + db_host + ":" + str(db_port) + " as " + db_user + "...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

def aggregate_errors(parsed_logs: List[Dict]) -> Dict[str, int]:
    """Aggregates error messages and their counts from parsed log data."""
    error_summary = {}
    for log_entry in parsed_logs:
        if log_entry.get("t") == "ERR":
            msg = log_entry["m"]
            error_summary[msg] = error_summary.get(msg, 0) + 1
    return error_summary

def proc_data():
    db_path = os.getenv("DB_PATH", "metrics.db")
    log_file = os.getenv("LOG_FILE", "server.log")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", 5432))
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")

    log_lines = load_logs(log_file)
    d_list, sessions, api_calls = process_raw_logs(log_lines)
    error_summary = aggregate_errors(d_list)

    print(f"d_list: {d_list}") # Debug print
    print(f"api_calls: {api_calls}") # Debug print

    print("Connecting to " + db_host + ":" + str(db_port) + " as " + db_user + "...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    print(f"r (error summary): {error_summary}") # Debug print

    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg, count)
        )

def calculate_api_latency(api_calls: List[Dict]) -> Dict[str, float]:
    """Calculates the average latency for each API endpoint."""
    endpoint_stats = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_stats.setdefault(ep, []).append(call["ms"])
    
    avg_latency = {ep: sum(times) / len(times) for ep, times in endpoint_stats.items()}
    return avg_latency

def proc_data():
    db_path = os.getenv("DB_PATH", "metrics.db")
    log_file = os.getenv("LOG_FILE", "server.log")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", 5432))
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")

    log_lines = load_logs(log_file)
    d_list, sessions, api_calls = process_raw_logs(log_lines)
    error_summary = aggregate_errors(d_list)
    api_latency = calculate_api_latency(api_calls)

    print(f"d_list: {d_list}") # Debug print
    print(f"api_calls: {api_calls}") # Debug print

    print("Connecting to " + db_host + ":" + str(db_port) + " as " + db_user + "...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    print(f"r (error summary): {error_summary}") # Debug print

    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg, count)
        )

    for ep, avg in api_latency.items():
        # SQL injection here too
        c.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ep, avg)
        )

    conn.commit()
    conn.close()

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += "<li><b>" + err_msg + "</b>: " + str(count) + " occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_latency.items():
        out += "<tr><td>" + ep + "</td><td>" + str(round(avg, 1)) + "</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += "<p>" + str(len(sessions)) + " user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

    print("Job finished at " + str(datetime.datetime.now()))


if __name__ == "__main__":
    log_file_path_main = os.getenv("LOG_FILE", "server.log")
    if not os.path.exists(log_file_path_main):
        with open(log_file_path_main, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    proc_data()
