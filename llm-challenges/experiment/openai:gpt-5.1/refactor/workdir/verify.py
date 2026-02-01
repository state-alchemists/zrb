#!/usr/bin/env python3
import os
import re
import subprocess
import sys


def verify_refactor():
    """Verify the refactor challenge."""

    # Check if etl.py exists
    if not os.path.exists("etl.py"):
        print("FAIL: etl.py not found")
        print("VERIFICATION_RESULT: FAIL")
        return False

    # Read the file
    with open("etl.py", "r") as f:
        content = f.read()

    checks = []

    # Grading components
    critical_checks_passed = True
    score = 0
    max_score = 5  # Functions, ETL, Config, Regex, TypeHints/Docstrings

    # Check for separation of concerns (functions/classes)
    function_count = len(re.findall(r"def\s+\w+\s*\(", content))
    class_count = len(re.findall(r"class\s+\w+\s*:", content))

    if function_count >= 3 or class_count >= 1:
        checks.append(("Separated into functions/classes", True))
        score += 1
    else:
        checks.append(("Separated into functions/classes", False))
        # This is arguably critical for a refactor
        critical_checks_passed = False

    # Check for Extract, Transform, Load pattern
    content_lower = content.lower()
    has_extract = "extract" in content_lower
    has_transform = "transform" in content_lower
    has_load = "load" in content_lower or "report" in content_lower

    if has_extract and has_transform and has_load:
        checks.append(("ETL pattern (Extract/Transform/Load)", True))
        score += 1
    else:
        checks.append(("ETL pattern (Extract/Transform/Load)", False))

    # Check for configuration decoupling
    if (
        "os.getenv" in content
        or "config" in content_lower
        or "settings" in content_lower
    ):
        checks.append(("Configuration decoupled", True))
        score += 1
    else:
        checks.append(("Configuration decoupled", False))

    # Check for regex usage
    if "import re" in content or "re." in content:
        checks.append(("Uses regex for parsing", True))
        score += 1
    else:
        checks.append(("Uses regex for parsing", False))

    # Check for type hints and docstrings (Combined point)
    has_types = (
        "->" in content
        or ": List" in content
        or ": Dict" in content
        or ": Optional" in content
    )
    has_docs = '"""' in content or "'''" in content

    if has_types and has_docs:
        checks.append(("Has type hints & docstrings", True))
        score += 1
    else:
        checks.append(
            (
                f"Has type hints & docstrings (Types: {has_types}, Docs: {has_docs})",
                False,
            )
        )

    # Check if script still runs - CRITICAL
    print("Testing if script runs...")
    script_runs = False
    try:
        # Create a dummy log file if not present (the script might do it, but let's ensure)
        with open("server.log", "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")

        result = subprocess.run(
            [sys.executable, "etl.py"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

        if result.returncode == 0:
            checks.append(("Script runs successfully", True))
            script_runs = True

            # Check if report.html is created
            if os.path.exists("report.html"):
                checks.append(("Creates report.html", True))
            else:
                checks.append(("Creates report.html", False))
                critical_checks_passed = False
        else:
            checks.append(("Script runs successfully", False))
            print(f"Script error: {result.stderr}")
            critical_checks_passed = False

    except Exception as e:
        checks.append(("Script runs successfully", False))
        print(f"Script test error: {e}")
        critical_checks_passed = False

    # Print results
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")

    if not critical_checks_passed or not script_runs:
        print("VERIFICATION_RESULT: FAIL")
        return False

    if score >= 4:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 2:
        print("VERIFICATION_RESULT: PASS")
    else:
        # Script runs but barely refactored
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify_refactor()
    sys.exit(0 if success else 1)
