#!/usr/bin/env python3
import os
import re
import subprocess
import sys


def verify_refactor():
    """Verify the refactor challenge."""

    # Check if legacy_etl.py exists
    if not os.path.exists("legacy_etl.py"):
        print("FAIL: legacy_etl.py not found")
        return False

    # Read the file
    with open("legacy_etl.py", "r") as f:
        content = f.read()

    checks = []

    # Check for separation of concerns (functions/classes)
    function_count = len(re.findall(r"def\s+\w+\s*\(", content))
    class_count = len(re.findall(r"class\s+\w+\s*:", content))

    if function_count >= 3 or class_count >= 1:
        checks.append(("Separated into functions/classes", True))
    else:
        checks.append(("Separated into functions/classes", False))

    # Check for Extract, Transform, Load pattern
    content_lower = content.lower()
    has_extract = "extract" in content_lower
    has_transform = "transform" in content_lower
    has_load = "load" in content_lower or "report" in content_lower

    if has_extract and has_transform and has_load:
        checks.append(("ETL pattern (Extract/Transform/Load)", True))
    else:
        checks.append(("ETL pattern (Extract/Transform/Load)", False))

    # Check for configuration decoupling
    if (
        "os.getenv" in content
        or "config" in content_lower
        or "settings" in content_lower
    ):
        checks.append(("Configuration decoupled", True))
    else:
        checks.append(("Configuration decoupled", False))

    # Check for regex usage
    if "import re" in content or "re." in content:
        checks.append(("Uses regex for parsing", True))
    else:
        checks.append(("Uses regex for parsing", False))

    # Check for type hints
    if (
        "->" in content
        or ": List" in content
        or ": Dict" in content
        or ": Optional" in content
    ):
        checks.append(("Has type hints", True))
    else:
        checks.append(("Has type hints", False))

    # Check for docstrings
    if '"""' in content or "'''" in content:
        checks.append(("Has docstrings", True))
    else:
        checks.append(("Has docstrings", False))

    # Check if script still runs
    print("Testing if script runs...")
    try:
        result = subprocess.run(
            [sys.executable, "legacy_etl.py"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

        if result.returncode == 0:
            checks.append(("Script runs successfully", True))

            # Check if report.html is created
            if os.path.exists("report.html"):
                checks.append(("Creates report.html", True))
            else:
                checks.append(("Creates report.html", False))
        else:
            checks.append(("Script runs successfully", False))
            print(f"Script error: {result.stderr}")

    except Exception as e:
        checks.append(("Script runs successfully", False))
        print(f"Script test error: {e}")

    # Check for setup separation
    if "if __name__" in content and "main" in content_lower:
        checks.append(("Main guard present", True))
    else:
        checks.append(("Main guard present", False))

    # Print results
    all_passed = True
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    success = verify_refactor()
    sys.exit(0 if success else 1)
