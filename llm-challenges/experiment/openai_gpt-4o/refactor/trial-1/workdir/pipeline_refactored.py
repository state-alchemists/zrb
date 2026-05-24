import os
import re
import datetime
import sqlite3
from typing import List, Dict, Any

# Configuration via environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")


class LogProcessor:
    """
    A class to process server logs and generate reports.
    """
    def __init__(self, db_path: str, log_file: str):
        self.db_path = db_path
        self.log_file = log_file

    def extract(self) -> Dict[str, Any]:
        """
        Extracts data from the log file using regex.

        Returns:
            Dict[str, Any]: Parsed data containing error, user session, and API call information.
        """
        error_patterns = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR) (.+)")
        user_patterns = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\d+) (.+)")
        api_patterns = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (\S+) took (\d+)ms")
        warn_patterns = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.+)")

        data = {'errors': [], 'sessions': {}, 'api_calls': []}

        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                for line in f:
                    if match := error_patterns.match(line):
                        dt, lvl, msg = match.groups()
                        data['errors'].append({'datetime': dt, 'message': msg})
                    elif match := user_patterns.match(line):
                        dt, user_id, action = match.groups()
                        if "logged in" in action:
                            data['sessions'][user_id] = dt
                        elif "logged out" in action and user_id in data['sessions']:
                            data['sessions'].pop(user_id)
                    elif match := api_patterns.match(line):
                        dt, endpoint, duration = match.groups()
                        data['api_calls'].append({'datetime': dt, 'endpoint': endpoint, 'duration': int(duration)})
                    elif match := warn_patterns.match(line):
                        dt, msg = match.groups()
                        data['errors'].append({'datetime': dt, 'message': "WARN: " + msg})

        return data

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforms the extracted data to summarize errors and calculate average API latencies.

        Args:
            data (Dict[str, Any]): The extracted data.

        Returns:
            Dict[str, Any]: Summarized error counts and API latencies.
        """
        error_summary = {}
        for error in data['errors']:
            msg = error['message']
            error_summary[msg] = error_summary.get(msg, 0) + 1

        endpoint_stats = {}
        for api_call in data['api_calls']:
            ep = api_call['endpoint']
            endpoint_stats.setdefault(ep, []).append(api_call['duration'])

        avg_latencies = {ep: sum(times) / len(times) for ep, times in endpoint_stats.items()}

        return {'errors': error_summary, 'api_metrics': avg_latencies, 'active_sessions': len(data['sessions'])}

    def load(self, transformed_data: Dict[str, Any]):
        """
        Loads the transformed data into the database and generates the HTML report.

        Args:
            transformed_data (Dict[str, Any]): The results to be written to the database and the report.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
            c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for msg, count in transformed_data['errors'].items():
                c.execute("INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)", (current_time, msg, count))

            for ep, avg in transformed_data['api_metrics'].items():
                c.execute("INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)", (current_time, ep, avg))

            conn.commit()

            report = ("<html><head><title>System Report</title></head><body>" +
                      "<h1>Error Summary</h1><ul>" +
                      "".join(f"<li><b>{msg}</b>: {count} occurrences</li>" for msg, count in transformed_data['errors'].items()) +
                      "</ul><h2>API Latency</h2><table border='1'><tr><th>Endpoint</th><th>Avg (ms)</th></tr>" +
                      "".join(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>" for ep, avg in transformed_data['api_metrics'].items()) +
                      "</table><h2>Active Sessions</h2><p>{transformed_data['active_sessions']} user(s) currently active</p></body></html>")

            with open("report.html", "w") as f:
                f.write(report)
        finally:
            conn.close()

    def process_logs(self):
        """
        Executes the full ETL process: Extract, Transform, Load.
        """
        extracted_data = self.extract()
        transformed_data = self.transform(extracted_data)
        self.load(transformed_data)


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    processor = LogProcessor(DB_PATH, LOG_FILE)
    processor.process_logs()
