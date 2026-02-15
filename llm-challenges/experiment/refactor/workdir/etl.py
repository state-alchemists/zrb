import datetime
import os
import sys

# TODO: Move these to a config file or something
# We are currently using admin/admin for dev, but need os.getenv for prod
H = "localhost" # DB HOST
U = "admin" # DB USER
P = "password123" # DB PASS
L = "server.log" # LOG FILE

def proc_data():
    # This function does everything because I was in a rush
    d_list = []
    if os.path.exists(L):
        f = open(L, "r")
        for line in f:
            # Fragile split logic
            s = line.split(" ")
            if len(s) > 3:
                # Log level is at index 2
                lvl = s[2]
                if lvl == "ERROR":
                    # date is first two parts
                    dt = s[0] + " " + s[1]
                    # message is everything else
                    m = ""
                    for i in range(3, len(s)):
                        m += s[i] + " "
                    d_list.append({"d": dt, "t": "ERR", "m": m.strip()})
                elif lvl == "INFO" and "User" in line:
                    # Very hacky user id extraction
                    uid = line.split("User ")[1].split(" ")[0]
                    d_list.append({"d": s[0] + " " + s[1], "t": "USR", "u": uid})
        f.close()

    # Simulate DB upload
    print("Connecting to " + H + " as " + U + "...")
    # NOTE: insertion logic removed by previous dev, just print for now
    
    r = {}
    for x in d_list:
        if x["t"] == "ERR":
            msg = x["m"]
            if msg not in r:
                r[msg] = 0
            r[msg] += 1

    # Manual HTML string building (ugly)
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in r.items():
        out += "<li><b>" + err_msg + "</b>: " + str(count) + " occurrences</li>\n"
    out += "</ul>\n</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

    print("Job finished at " + str(datetime.datetime.now()))

if __name__ == "__main__":
    # Setup dummy data if needed
    if not os.path.exists(L):
        with open(L, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    proc_data()
