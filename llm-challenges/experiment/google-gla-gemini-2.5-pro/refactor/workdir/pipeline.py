import datetime
import os
import sqlite3

# Hardcoded config — change these manually for each environment
DB_PATH = "metrics.db"
LOG_FILE = "server.log"
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "admin"
DB_PASS = "password123"


def proc_data():
    d_list = []
    sessions = {}
    api_calls = []

    if os.path.exists(LOG_FILE):
        f = open(LOG_FILE, "r")
        for line in f:
            s = line.split(" ")
            if len(s) > 3:
                lvl = s[2]
                dt = s[0] + " " + s[1]

                if lvl == "ERROR":
                    m = ""
                    for i in range(3, len(s)):
                        m += s[i] + " "
                    d_list.append({"d": dt, "t": "ERR", "m": m.strip()})

                elif lvl == "INFO" and "User" in line:
                    uid = line.split("User ")[1].split(" ")[0]
                    action = line.split("User " + uid + " ")[1].strip()
                    if "logged in" in action:
                        sessions[uid] = dt
                    elif "logged out" in action and uid in sessions:
                        sessions.pop(uid)
                    d_list.append({"d": dt, "t": "USR", "u": uid, "a": action})

                elif lvl == "INFO" and "API" in line:
                    endpoint = line.split("API ")[1].split(" ")[0]
                    dur = line.split("took ")[1].split("ms")[0] if "took" in line else "0"
                    api_calls.append({"d": dt, "endpoint": endpoint, "ms": int(dur)})

                elif lvl == "WARN":
                    m = " ".join(s[3:]).strip()
                    d_list.append({"d": dt, "t": "WARN", "m": m})
        f.close()

    print("Connecting to " + DB_HOST + ":" + str(DB_PORT) + " as " + DB_USER + "...")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    r = {}
    for x in d_list:
        if x["t"] == "ERR":
            msg = x["m"]
            r[msg] = r.get(msg, 0) + 1

    for msg, count in r.items():
        # SQL injection: string formatting instead of parameterized query
        c.execute(
            "INSERT INTO errors VALUES ('%s', '%s', %d)"
            % (datetime.datetime.now(), msg, count)
        )

    endpoint_stats = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_stats.setdefault(ep, []).append(call["ms"])

    for ep, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        # SQL injection here too
        c.execute(
            "INSERT INTO api_metrics VALUES ('%s', '%s', %f)"
            % (datetime.datetime.now(), ep, avg)
        )

    conn.commit()
    conn.close()

    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in r.items():
        out += "<li><b>" + err_msg + "</b>: " + str(count) + " occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        out += "<tr><td>" + ep + "</td><td>" + str(round(avg, 1)) + "</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += "<p>" + str(len(sessions)) + " user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

    print("Job finished at " + str(datetime.datetime.now()))


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
