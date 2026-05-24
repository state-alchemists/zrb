import os
import re
import datetime
import sqlite3
from typing import List, Dict, Any


def get_env_vars() -> Dict[str, str]:
    """Retrieve configuration from environment variables."""
    return {
        'DB_PATH': os.getenv('DB_PATH', 'metrics.db'),
        'LOG_FILE': os.getenv('LOG_FILE', 'server.log'),
        'DB_HOST': os.getenv('DB_HOST', 'localhost'),
        'DB_PORT': os.getenv('DB_PORT', '5432'),
        'DB_USER': os.getenv('DB_USER', 'admin'),
        'DB_PASS': os.getenv('DB_PASS', 'password123')
    }


def parse_log_file(log_file_path: str) -> Dict[str, Any]:
    """Parse the log file and categorize the log entries."""
    log_patterns = {
        'ERROR': re.compile(r'^(\S+ \S+) ERROR (.*)$'),
        'USER': re.compile(r'^(\S+ \S+) INFO User (\d+) (logged in|logged out)$'),
        'API': re.compile(r'^(\S+ \S+) INFO API (\S+) took (\d+)ms$'),
        'WARN': re.compile(r'^(\S+ \S+) WARN (.*)$')
    }

    data = {'errors': [], 'sessions': {}, 'api_calls': []}

    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as log_file:
            for line in log_file:
                for log_type, pattern in log_patterns.items():
                    match = pattern.match(line)
                    if match:
                        if log_type == 'ERROR':
                            data['errors'].append({'datetime': match.group(1), 'message': match.group(2)})
                        elif log_type == 'USER':
                            datetime, user_id, action = match.groups()
                            if action == 'logged in':
                                data['sessions'][user_id] = datetime
                            elif action == 'logged out' and user_id in data['sessions']:
                                del data['sessions'][user_id]
                        elif log_type == 'API':
                            data['api_calls'].append({'datetime': match.group(1), 'endpoint': match.group(2), 'ms': int(match.group(3))})
                        elif log_type == 'WARN':
                            data['errors'].append({'datetime': match.group(1), 'message': match.group(2)})
                        
    return data


def transform_data(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform parsed data for database insertion and reporting."""
    error_count = {}
    api_stats = {}

    for error in parsed_data['errors']:
        msg = error['message']
        error_count[msg] = error_count.get(msg, 0) + 1

    for call in parsed_data['api_calls']:
        endpoint = call['endpoint']
        api_stats.setdefault(endpoint, []).append(call['ms'])

    return {'errors': error_count, 'api_metrics': {ep: sum(times) / len(times) for ep, times in api_stats.items()}, 'sessions': parsed_data['sessions']}


def load_data_to_db(transformed_data: Dict[str, Any], db_config: Dict[str, str]):
    """Load transformed data into the database using parameterized queries."""
    conn = sqlite3.connect(db_config['DB_PATH'])
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    current_time = datetime.datetime.now().isoformat()

    for message, count in transformed_data['errors'].items():
        cursor.execute("INSERT INTO errors VALUES (?, ?, ?)", (current_time, message, count))

    for endpoint, avg_ms in transformed_data['api_metrics'].items():
        cursor.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (current_time, endpoint, avg_ms))

    conn.commit()
    conn.close()


def generate_report(transformed_data: Dict[str, Any]):
    """Generate a HTML report from the transformed data."""
    report = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    report += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in transformed_data['errors'].items():
        report += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    report += "</ul>\n"

    report += "<h2>API Latency</h2>\n<table border='1'>\n<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in transformed_data['api_metrics'].items():
        report += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    report += "</table>\n"

    report += "<h2>Active Sessions</h2>\n<p>" + str(len(transformed_data['sessions'])) + " user(s) currently active</p>\n"
    report += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(report)


def main():
    config = get_env_vars()
    parsed_data = parse_log_file(config['LOG_FILE'])
    transformed_data = transform_data(parsed_data)
    load_data_to_db(transformed_data, config)
    generate_report(transformed_data)
    print("Job finished at " + str(datetime.datetime.now()))


if __name__ == "__main__":
    main()
