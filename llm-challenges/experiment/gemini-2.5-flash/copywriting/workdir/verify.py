#!/usr/bin/env python3
import os
import re
import sys


def verify_copywriting():
    """Verify the copywriting challenge."""

    # Check if launch_post.md exists
    if not os.path.exists("launch_post.md"):
        print("FAIL: launch_post.md not found")
        return False

    # Read the file
    with open("launch_post.md", "r") as f:
        content = f.read()

    # Check for required elements
    checks = []

    # Check structure elements
    if "# " in content or "## " in content:
        checks.append(("Has headings", True))
    else:
        checks.append(("Has headings", False))

    # Check for product details
    required_terms = [
        "Zrb-Flow",
        "AI",
        "workflow",
        "automation",
        "CLI",
        "Docker",
        "K8s",
        "Kubernetes",
        "Python",
        "Self-Healing",
        "pipeline",
    ]

    for term in required_terms:
        if term.lower() in content.lower():
            checks.append((f"Contains '{term}'", True))
        else:
            checks.append((f"Contains '{term}'", False))

    # Check for call to action
    cta_terms = ["install", "try", "get started", "download", "sign up"]
    has_cta = any(term.lower() in content.lower() for term in cta_terms)
    checks.append(("Has call to action", has_cta))

    # Check markdown formatting
    lines = content.split("\n")
    markdown_errors = []
    for i, line in enumerate(lines):
        if line.strip().startswith("#") and " " not in line.strip()[1:]:
            markdown_errors.append(f"Line {i+1}: Heading without space after #")

    checks.append(("Markdown formatting", len(markdown_errors) == 0))

    # Print results
    all_passed = True
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    if markdown_errors:
        print("\nMarkdown errors:")
        for error in markdown_errors:
            print(f"  - {error}")

    return all_passed


if __name__ == "__main__":
    success = verify_copywriting()
    sys.exit(0 if success else 1)
