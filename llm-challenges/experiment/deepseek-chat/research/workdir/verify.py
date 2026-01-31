#!/usr/bin/env python3
import os
import re
import sys


def verify_research():
    """Verify the research challenge."""

    # Check if report exists
    report_path = "solid_state_battery_report.md"
    if not os.path.exists(report_path):
        print(f"FAIL: {report_path} not found")
        return False

    # Read the file
    with open(report_path, "r") as f:
        content = f.read()

    checks = []

    # Check for markdown format
    if content.strip().startswith("#") or "##" in content:
        checks.append(("Markdown format", True))
    else:
        checks.append(("Markdown format", False))

    # Check for required sections
    content_lower = content.lower()

    # Check for timeline/commercial viability
    timeline_terms = [
        "timeline",
        "2024",
        "2025",
        "commercial",
        "viability",
        "car",
        "vehicle",
        "production",
    ]
    has_timeline = any(term in content_lower for term in timeline_terms)
    checks.append(("Covers timeline/commercial viability", has_timeline))

    # Check for key players
    player_terms = [
        "company",
        "toyota",
        "panasonic",
        "samsung",
        "lg",
        "quantumscape",
        "solid power",
        "player",
        "manufacturer",
    ]
    has_players = any(term in content_lower for term in player_terms)
    checks.append(("Covers key players", has_players))

    # Check for technical hurdles
    hurdle_terms = [
        "hurdle",
        "challenge",
        "technical",
        "issue",
        "problem",
        "density",
        "cycle",
        "cost",
        "manufacturing",
    ]
    has_hurdles = any(term in content_lower for term in hurdle_terms)
    checks.append(("Covers technical hurdles", has_hurdles))

    # Check structure
    lines = content.split("\n")
    headers = [line for line in lines if line.strip().startswith("#")]

    if len(headers) >= 3:
        checks.append(("Has multiple sections/headers", True))
    else:
        checks.append(("Has multiple sections/headers", False))

    # Check for plausible information (basic sanity)
    word_count = len(content.split())
    if word_count > 200:
        checks.append(("Substantial content (200+ words)", True))
    else:
        checks.append(("Substantial content (200+ words)", False))

    # Check for citations/sources (optional but good)
    if "http" in content or "source" in content_lower or "reference" in content_lower:
        checks.append(("References/citations", True))
    else:
        checks.append(("References/citations", False))

    # Print results
    all_passed = True
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    success = verify_research()
    sys.exit(0 if success else 1)
