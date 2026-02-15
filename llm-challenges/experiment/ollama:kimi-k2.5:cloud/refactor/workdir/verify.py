#!/usr/bin/env python3
import os
import re
import subprocess
import sys


def verify_refactor():
    """Verify the refactor challenge."""

    # Candidate files for the refactored script
    candidates = ["etl.py", "etl_refactored.py", "main.py"]
    refactor_file = None
    
    # Find the best candidate (prefer etl_refactored.py if it exists, otherwise etl.py)
    if os.path.exists("etl_refactored.py"):
        refactor_file = "etl_refactored.py"
    elif os.path.exists("etl.py"):
        refactor_file = "etl.py"
    else:
        # Check for any other python file that might be the one
        for f in os.listdir("."):
            if f.endswith(".py") and f not in ["verify.py", "account.py", "bank.py", "inventory_system.py"]:
                refactor_file = f
                break

    if not refactor_file:
        print("FAIL: Refactored script not found")
        print("VERIFICATION_RESULT: FAIL")
        return False

    print(f"Verifying refactored script: {refactor_file}")

    # Read the file
    with open(refactor_file, "r") as f:
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
        or "environ" in content
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
        or ": str" in content
        or ": int" in content
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
            [sys.executable, refactor_file],
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
