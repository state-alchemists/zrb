import datetime
import os
import sys

# Global config
DB_HOST = "localhost"
DB_USER = "admin"
LOG_FILE = "server.log"


def do_everything():
    data = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            for l in lines:
                parts = l.split(" ")
                if len(parts) > 3:
                    if parts[2] == "ERROR":
                        # Bad way to parse date
                        d = parts[0] + " " + parts[1]
                        msg = " ".join(parts[3:]).strip()
                        data.append({"date": d, "type": "ERROR", "msg": msg})
                    elif parts[2] == "INFO":
                        d = parts[0] + " " + parts[1]
                        msg = " ".join(parts[3:]).strip()
                        if "User" in msg:
                            user_id = msg.split("User")[1].split(" ")[1]
                            data.append(
                                {"date": d, "type": "USER_ACTION", "user": user_id}
                            )

    # "Simulate" database connection and insertion
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    report = {}
    for item in data:
        if item["type"] == "ERROR":
            if item["msg"] not in report:
                report[item["msg"]] = 0
            report[item["msg"]] += 1

    # Generate HTML report manually
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"

    with open("report.html", "w") as f:
        f.write(html)

    print("Done.")


if __name__ == "__main__":
    # Create dummy log file if not exists for testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    do_everything()
