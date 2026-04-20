import datetime
import os
import sqlite3
import re

# Hardcoded config — change these manually for each environment




def parse_log_file(log_file_path: str) -> tuple[list[dict], dict[str, str], list[dict]]:
    """
    Parses the server log file, extracting error messages, user sessions, and API call details.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A tuple containing:
            - d_list: A list of dictionaries for errors, user actions, and warnings.
            - sessions: A dictionary tracking active user sessions.
            - api_calls: A list of dictionaries for API call details (endpoint, latency).
    """
    d_list: list[dict] = []
    sessions: dict[str, str] = {}
    api_calls: list[dict] = []

    if not os.path.exists(log_file_path):
        return d_list, sessions, api_calls

    log_pattern = re.compile(r'^(?P<datetime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<message>.*)$')
    user_login_pattern = re.compile(r'User (?P<user_id>\d+) logged in')
    user_logout_pattern = re.compile(r'User (?P<user_id>\d+) logged out')
    api_call_pattern = re.compile(r'API (?P<endpoint>/[\w\-/]+) took (?P<duration>\d+)ms')

    with open(log_file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if not match:
                continue

            dt = match.group("datetime")
            level = match.group("level")
            message = match.group("message")

            if level == "ERROR":
                d_list.append({"d": dt, "t": "ERR", "m": message.strip()})

            elif level == "INFO":
                user_login_match = user_login_pattern.search(message)
                user_logout_match = user_logout_pattern.search(message)
                api_call_match = api_call_pattern.search(message)

                if user_login_match:
                    uid = user_login_match.group("user_id")
                    sessions[uid] = dt
                    d_list.append({"d": dt, "t": "USR", "u": uid, "a": f"User {uid} logged in"})
                elif user_logout_match:
                    uid = user_logout_match.group("user_id")
                    if uid in sessions:
                        sessions.pop(uid)
                    d_list.append({"d": dt, "t": "USR", "u": uid, "a": f"User {uid} logged out"})
                elif api_call_match:
                    endpoint = api_call_match.group("endpoint")
                    dur = int(api_call_match.group("duration"))
                    api_calls.append({"d": dt, "endpoint": endpoint, "ms": dur})

            elif level == "WARN":
                d_list.append({"d": dt, "t": "WARN", "m": message.strip()})
    return d_list, sessions, api_calls

def summarize_errors(d_list: list[dict]) -> dict[str, int]:
    """
    Summarizes error messages and counts their occurrences.

    Args:
        d_list: A list of parsed log entries.

    Returns:
        A dictionary where keys are error messages and values are their counts.
    """
    error_summary: dict[str, int] = {}
    for x in d_list:
        if x["t"] == "ERR":
            msg = x["m"]
            error_summary[msg] = error_summary.get(msg, 0) + 1
    return error_summary

def calculate_api_latency(api_calls: list[dict]) -> dict[str, float]:
    """
    Calculates the average latency for each API endpoint.

    Args:
        api_calls: A list of dictionaries containing API call details.

    Returns:
        A dictionary where keys are API endpoints and values are their average latencies in ms.
    """
    endpoint_stats: dict[str, list[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_stats.setdefault(ep, []).append(call["ms"])

    api_latency_stats: dict[str, float] = {}
    for ep, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        api_latency_stats[ep] = avg
    return api_latency_stats

def store_metrics(error_summary: dict[str, int], api_latency_stats: dict[str, float], db_path: str, db_host: str, db_port: int, db_user: str) -> None:
    """
    Stores error and API latency metrics into an SQLite database.

    Args:
        error_summary: A dictionary of error messages and their counts.
        api_latency_stats: A dictionary of API endpoints and their average latencies.
        db_path: Path to the SQLite database file.
        db_host: Database host (for logging purposes, not used by sqlite3).
        db_port: Database port (for logging purposes, not used by sqlite3).
        db_user: Database user (for logging purposes, not used by sqlite3).
    """
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (datetime.datetime.now(), msg, count)
        )

    for ep, avg in api_latency_stats.items():
        c.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (datetime.datetime.now(), ep, avg)
        )

    conn.commit()
    conn.close()

def generate_html_report(error_summary: dict[str, int], api_latency_stats: dict[str, float], active_sessions_count: int) -> None:
    """
    Generates an HTML report summarizing errors, API latencies, and active sessions.

    Args:
        error_summary: A dictionary of error messages and their counts.
        api_latency_stats: A dictionary of API endpoints and their average latencies.
        active_sessions_count: The number of currently active user sessions.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_latency_stats.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

def main():
    DB_PATH = os.getenv("DB_PATH", "metrics.db")
    LOG_FILE = os.getenv("LOG_FILE", "server.log")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASS = os.getenv("DB_PASS", "password123")

    d_list, sessions, api_calls = parse_log_file(LOG_FILE)

    error_summary = summarize_errors(d_list)
    api_latency_stats = calculate_api_latency(api_calls)

    store_metrics(error_summary, api_latency_stats, DB_PATH, DB_HOST, DB_PORT, DB_USER)
    generate_html_report(error_summary, api_latency_stats, len(sessions))

    print("Job finished at " + str(datetime.datetime.now()))

if __name__ == "__main__":
    # Ensure LOG_FILE is set for the initial log creation
    log_file = os.getenv("LOG_FILE", "server.log")
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()