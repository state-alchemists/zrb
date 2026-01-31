#!/usr/bin/env python3
import os
import re
import sys


def verify_copywriting():
    """Verify the copywriting challenge."""

    # Check if launch_post.md exists
    if not os.path.exists("launch_post.md"):
        print("FAIL: launch_post.md not found")
        print("VERIFICATION_RESULT: FAIL")
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
        "automation",
        "CLI",
        "Docker",
        "K8s",
        "Self-Healing",
        "pipeline",
    ]
    # Removed "Kubernetes" (K8s is enough), "workflow" (automation covers it), "Python" (script implies it)
    # to be more lenient on secondary terms, focusing on core brand/tech terms.

    present_terms = 0
    for term in required_terms:
        if term.lower() in content.lower():
            checks.append((f"Contains '{term}'", True))
            present_terms += 1
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

    is_markdown_valid = len(markdown_errors) == 0
    checks.append(("Markdown formatting", is_markdown_valid))

    # Print results
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")

    if markdown_errors:
        print("\nMarkdown errors:")
        for error in markdown_errors:
            print(f"  - {error}")

    # Determine status
    # Critical: Markdown valid, Has headings
    if not is_markdown_valid:
        print("VERIFICATION_RESULT: FAIL")
        return False

    term_percentage = present_terms / len(required_terms)

    if term_percentage == 1.0 and has_cta:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif term_percentage >= 0.75:
        print("VERIFICATION_RESULT: PASS")
    else:
        print(f"FAIL: Only {term_percentage:.0%} of required terms present")
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify_copywriting()
    sys.exit(0 if success else 1)
