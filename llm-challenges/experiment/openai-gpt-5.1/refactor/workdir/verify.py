#!/usr/bin/env python3
import os
import re
import subprocess
import sys


def verify():
    print("Verifying Pipeline Refactor...")

    # Accept pipeline.py, pipeline_refactored.py, or any non-system .py file
    candidates = ["pipeline_refactored.py", "pipeline.py"]
    refactor_file = None
    for c in candidates:
        if os.path.exists(c):
            refactor_file = c
            break
    if not refactor_file:
        for f in os.listdir("."):
            if f.endswith(".py") and f not in ["verify.py"]:
                refactor_file = f
                break

    if not refactor_file:
        print("FAIL: No refactored script found")
        print("VERIFICATION_RESULT: FAIL")
        return False

    print(f"Checking: {refactor_file}")
    with open(refactor_file) as f:
        content = f.read()

    content_lower = content.lower()
    score = 0
    critical_ok = True
    missed: list[str] = []

    # 1. Env vars used
    if "os.getenv" in content or "os.environ" in content:
        print("PASS: Environment variables used for config")
        score += 1
    else:
        print("FAIL: No os.getenv / os.environ found — credentials still hardcoded")
        missed.append("env-var-based config")

    # 1b. Hardcoded credentials must be removed — CRITICAL.
    # Catches os.getenv("DB_PASS", "password123") and similar half-fixes
    # that satisfy the env-var check while still leaking the original value.
    if "password123" in content:
        print("FAIL: Hardcoded credential 'password123' still present in source")
        critical_ok = False

    # 2. No SQL injection (no string formatting inside execute calls)
    sql_lines = [l for l in content.split("\n") if "execute(" in l.lower()]
    injection_patterns = [r"execute\s*\(.*%[sdf]", r"execute\s*\(.*\+", r"execute\s*\(f[\"']"]
    has_injection = any(
        re.search(pat, line) for line in sql_lines for pat in injection_patterns
    )
    if not has_injection and sql_lines:
        print("PASS: SQL queries use parameterized form (no injection)")
        score += 1
    elif not sql_lines:
        print("INFO: No SQL execute() calls found — skipping injection check")
        score += 1
    else:
        print("FAIL: SQL injection risk — string formatting detected in execute() call")
        critical_ok = False

    # 3. ETL pattern (extract / transform / load separation)
    has_extract = "extract" in content_lower
    has_transform = "transform" in content_lower
    has_load = "load" in content_lower or "report" in content_lower
    if has_extract and has_transform and has_load:
        print("PASS: ETL pattern present (extract/transform/load)")
        score += 1
    else:
        print(f"FAIL: ETL pattern incomplete (extract={has_extract}, transform={has_transform}, load={has_load})")
        missed.append("ETL pattern (extract/transform/load)")

    # 4. Multiple functions or class (separation of concerns)
    fn_count = len(re.findall(r"^def\s+\w+", content, re.MULTILINE))
    class_count = len(re.findall(r"^class\s+\w+", content, re.MULTILINE))
    if fn_count >= 3 or class_count >= 1:
        print(f"PASS: Separated into {fn_count} function(s), {class_count} class(es)")
        score += 1
    else:
        print(f"FAIL: Only {fn_count} function(s) and no classes — needs more separation")
        missed.append("separation of concerns (≥3 functions or a class)")

    # 5. Regex used for parsing
    if "import re" in content or re.search(r"\bre\.(search|match|findall|compile)", content):
        print("PASS: Regex used for log parsing")
        score += 1
    else:
        print("FAIL: No regex found — fragile string.split() parsing still present")
        missed.append("regex log parsing")

    # 6. Type hints and docstrings
    has_types = bool(re.search(r"->\s*\w|\:\s*(str|int|float|List|Dict|Optional|bool)", content))
    has_docs = '"""' in content or "'''" in content
    if has_types and has_docs:
        print("PASS: Type hints and docstrings present")
        score += 1
    else:
        print(f"FAIL: Missing type hints ({has_types}) or docstrings ({has_docs})")
        missed.append("type hints + docstrings")

    # 7. Script runs and produces report.html — CRITICAL
    print("Running script...")
    log_path = os.path.join(os.path.dirname(os.path.abspath(refactor_file)), "server.log")
    with open(log_path, "w") as lf:
        lf.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        lf.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        lf.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        lf.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        lf.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        lf.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    try:
        result = subprocess.run(
            [sys.executable, refactor_file],
            capture_output=True, text=True, timeout=15,
            cwd=os.path.dirname(os.path.abspath(refactor_file)),
            env={
                **os.environ,
                "LOG_FILE": "server.log",
                "DB_PATH": "metrics.db",
                "DB_HOST": "localhost",
                "DB_PORT": "5432",
                "DB_USER": "admin",
                "DB_PASS": "password123",
            },
        )
        if result.returncode == 0:
            print("PASS: Script runs successfully")
            score += 1
        else:
            print(f"FAIL: Script exited with {result.returncode}")
            print(result.stderr[:500])
            critical_ok = False
    except Exception as e:
        print(f"FAIL: Script execution error: {e}")
        critical_ok = False

    # 8. report.html created with correct content — CRITICAL.
    # Two layers: required section names AND behavioral data points derived
    # from the fixed log fixture. The data-point layer prevents a model from
    # writing stub HTML containing the section words but no real output.
    if os.path.exists("report.html"):
        with open("report.html") as f:
            html = f.read().lower()
        has_errors = "error" in html
        has_latency = "latency" in html or "api" in html
        has_sessions = "session" in html
        section_ok = has_errors and has_latency and has_sessions

        expected_data = [
            ("database timeout", "error message from log"),
            ("/users/profile", "API endpoint from log"),
            ("250", "API latency value from log"),
        ]
        missing_behavioral = [
            label for needle, label in expected_data if needle not in html
        ]

        if section_ok and not missing_behavioral:
            print("PASS: report.html contains required sections and preserves source data")
            score += 1
        else:
            if not section_ok:
                print(
                    f"FAIL: report.html missing sections "
                    f"(errors={has_errors}, latency={has_latency}, sessions={has_sessions})"
                )
            if missing_behavioral:
                print(
                    f"FAIL: report.html behaviorally diverged from source — "
                    f"missing: {', '.join(missing_behavioral)}"
                )
            critical_ok = False
    else:
        print("FAIL: report.html not generated")
        critical_ok = False

    print(f"\nScore: {score}/8")
    if not critical_ok:
        print("VERIFICATION_RESULT: FAIL")
        return False
    if score >= 7:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 5:
        missing_str = "; ".join(missed) if missed else "n/a"
        print(
            f"WARN: Score {score}/8 — need ≥7 for EXCELLENT. "
            f"Missing: {missing_str}"
        )
        print("VERIFICATION_RESULT: PASS")
    else:
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
