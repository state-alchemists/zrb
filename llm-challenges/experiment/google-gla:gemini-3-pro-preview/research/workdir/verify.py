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
        print("VERIFICATION_RESULT: FAIL")
        return False

    # Read the file
    with open(report_path, "r") as f:
        content = f.read()

    checks = []

    score = 0
    max_score = 6

    # Critical Checks

    # Check for markdown format
    if content.strip().startswith("#") or "##" in content:
        checks.append(("Markdown format", True))
        score += 1
    else:
        checks.append(("Markdown format", False))

    # Check for Substantial content (200+ words)
    word_count = len(content.split())
    if word_count > 200:
        checks.append(("Substantial content (200+ words)", True))
        score += 1
    else:
        checks.append(("Substantial content (200+ words)", False))

    # Content Checks
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
    if has_timeline:
        score += 1

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
    if has_players:
        score += 1

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
        "dendrite",
        "interface",
    ]
    has_hurdles = any(term in content_lower for term in hurdle_terms)
    checks.append(("Covers technical hurdles", has_hurdles))
    if has_hurdles:
        score += 1

    # Check for citations/sources (This distinguishes Excellent vs Pass)
    has_citations = (
        "http" in content
        or "source" in content_lower
        or "reference" in content_lower
        or "[" in content
    )  # [1] style
    checks.append(("References/citations", has_citations))
    if has_citations:
        score += 1

    # Print results
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")

    # Determine status
    if not (has_timeline and has_players and has_hurdles):
        print("VERIFICATION_RESULT: FAIL")  # Missing core requirements
        return False

    if score == 6:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 5:  # Maybe missing citations or weak formatting but good content
        print("VERIFICATION_RESULT: PASS")
    else:
        print("VERIFICATION_RESULT: PASS")  # Be generous if content is there

    return True


if __name__ == "__main__":
    success = verify_research()
    sys.exit(0 if success else 1)
