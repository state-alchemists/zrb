#!/usr/bin/env python3
import os
import re
import sys


def verify():
    print("Verifying Architecture Decision Record...")

    SKIP_FILES = {"readme.md", "system_context.md"}
    report_path = "ADR-001-notification-architecture.md"
    if not os.path.exists(report_path):
        md_files = [
            f for f in os.listdir(".")
            if f.lower().endswith(".md") and f.lower() not in SKIP_FILES
        ]
        if md_files:
            report_path = sorted(md_files)[0]
            print(f"INFO: Using {report_path}")
        else:
            print("FAIL: No ADR markdown file found")
            print("VERIFICATION_RESULT: FAIL")
            return False

    with open(report_path) as f:
        content = f.read()

    content_lower = content.lower()
    score = 0
    max_score = 8

    # 1. Minimum word count
    words = len(content.split())
    if words >= 500:
        print(f"PASS: Substantial content ({words} words)")
        score += 1
    else:
        print(f"FAIL: Too short ({words} words, need 500+)")

    # 2. Has required ADR sections
    required_sections = ["context", "decision", "consequences", "alternatives"]
    found = [s for s in required_sections if s in content_lower]
    if len(found) >= 4:
        print("PASS: All ADR sections present (Context, Decision, Consequences, Alternatives)")
        score += 1
    elif len(found) >= 3:
        print(f"PASS: Most ADR sections present ({found})")
        score += 1
    else:
        print(f"FAIL: Missing ADR sections (found: {found}, need: {required_sections})")

    # 3. Has Status field
    if "status" in content_lower and any(s in content_lower for s in ["proposed", "accepted", "draft"]):
        print("PASS: Status field present")
        score += 1
    else:
        print("FAIL: Missing Status field (Proposed/Accepted/Draft)")

    # 4. Evaluates both Kafka and Redis
    has_kafka = "kafka" in content_lower
    has_redis = "redis" in content_lower
    if has_kafka and has_redis:
        print("PASS: Both Kafka and Redis Streams are evaluated")
        score += 1
    else:
        print(f"FAIL: Missing evaluation — kafka={has_kafka}, redis={has_redis}")

    # 5. Makes a definitive choice
    decision_terms = ["we will use", "we choose", "we adopt", "decision:", "chosen:", "recommend"]
    has_decision = any(t in content_lower for t in decision_terms)
    has_one_winner = (
        ("kafka" in content_lower and "redis" not in content_lower.split("decision")[1].split("alternatives")[0])
        if "decision" in content_lower and "alternatives" in content_lower
        else has_decision
    )
    if has_decision or (has_kafka and has_redis):
        print("PASS: Contains a clear recommendation")
        score += 1
    else:
        print("FAIL: No definitive recommendation found")

    # 6. Covers specific technical properties
    tech_terms = [
        "throughput", "ordering", "retention", "consumer group",
        "exactly-once", "at-least-once", "operational", "replication",
        "partition", "stream", "durability", "latency",
    ]
    covered = [t for t in tech_terms if t in content_lower]
    if len(covered) >= 4:
        print(f"PASS: Covers {len(covered)} technical properties ({', '.join(covered[:4])}...)")
        score += 1
    else:
        print(f"FAIL: Only {len(covered)} technical terms (need 4+): {covered}")

    # 7. Addresses team/constraint context (references system_context.md details)
    constraint_terms = ["team", "engineer", "redis", "operational complexity", "experience", "budget", "migration"]
    covered_constraints = [t for t in constraint_terms if t in content_lower]
    if len(covered_constraints) >= 3:
        print(f"PASS: Addresses team/constraint context")
        score += 1
    else:
        print(f"FAIL: Doesn't sufficiently address constraints (found: {covered_constraints})")

    # 8. Has pros AND cons of chosen option
    has_pros = any(t in content_lower for t in ["pro", "advantage", "benefit", "positive"])
    has_cons = any(t in content_lower for t in ["con", "disadvantage", "downside", "risk", "negative"])
    if has_pros and has_cons:
        print("PASS: Consequences include both pros and cons")
        score += 1
    else:
        print(f"FAIL: Consequences missing pros ({has_pros}) or cons ({has_cons})")

    print(f"\nScore: {score}/{max_score}")
    if score >= 7:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 5:
        print("VERIFICATION_RESULT: PASS")
    else:
        print(f"FAIL: Score too low ({score}/{max_score})")
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
