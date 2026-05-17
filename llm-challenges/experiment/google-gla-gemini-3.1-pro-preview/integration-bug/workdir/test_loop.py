import subprocess

for i in range(20):
    res = subprocess.run(["python", "main.py"], capture_output=True, text=True)
    if "ERROR" in res.stdout:
        print(f"Run {i} failed:")
        print(res.stdout)
        break
else:
    print("All runs successful.")
