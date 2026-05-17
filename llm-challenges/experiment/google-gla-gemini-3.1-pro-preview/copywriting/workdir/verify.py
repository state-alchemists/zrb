#!/usr/bin/env python3
import os
import re
import sys


def verify():
    print("Verifying Migration Guide...")

    report_path = "MIGRATION.md"
    if not os.path.exists(report_path):
        md_files = [f for f in os.listdir(".") if f.lower().endswith(".md") and "migration" in f.lower()]
        if md_files:
            report_path = md_files[0]
            print(f"INFO: Using {report_path}")
        else:
            print("FAIL: MIGRATION.md not found")
            print("VERIFICATION_RESULT: FAIL")
            return False

    with open(report_path) as f:
        content = f.read()

    content_lower = content.lower()
    score = 0
    max_score = 8
    missed: list[str] = []

    # 1. Has headings
    if re.search(r"^#{1,3} ", content, re.MULTILINE):
        print("PASS: Has markdown headings")
        score += 1
    else:
        print("FAIL: No markdown headings found")
        missed.append("markdown headings")

    # 2. Word count > 400
    word_count = len(content.split())
    if word_count >= 400:
        print(f"PASS: Substantial content ({word_count} words)")
        score += 1
    else:
        print(f"FAIL: Too short ({word_count} words, need 400+)")
        missed.append("≥400 words")

    # 3. Has fenced code blocks (before/after examples)
    code_blocks = re.findall(r"```", content)
    if len(code_blocks) >= 6:
        print(f"PASS: Has code examples ({len(code_blocks)//2} blocks)")
        score += 1
    else:
        print(f"FAIL: Needs at least 3 code blocks, found {len(code_blocks)//2}")
        missed.append("≥3 code blocks")

    # 4. Covers auth header change
    if "authorization" in content_lower and "bearer" in content_lower:
        print("PASS: Auth header change (Authorization: Bearer) documented")
        score += 1
    else:
        print("FAIL: Auth header change not documented (missing 'Authorization' or 'Bearer')")
        missed.append("Authorization: Bearer header change")

    # 5. Covers id type change to UUID
    if "uuid" in content_lower:
        print("PASS: ID type change (UUID) documented")
        score += 1
    else:
        print("FAIL: UUID id type change not mentioned")
        missed.append("UUID id type change")

    # 6. Covers field rename done → completed
    if "completed" in content_lower and ("done" in content_lower or "renamed" in content_lower):
        print("PASS: Field rename (done → completed) documented")
        score += 1
    else:
        print("FAIL: Field rename done→completed not documented")
        missed.append("field rename done→completed")

    # 7. Covers project_id requirement and /v2/ prefix
    if "project_id" in content_lower and "/v2" in content_lower:
        print("PASS: New project_id field and /v2/ prefix documented")
        score += 1
    else:
        print("FAIL: Missing project_id or /v2/ prefix documentation")
        missed.append("project_id field + /v2/ prefix")

    # 8. Has checklist or upgrade command
    has_checklist = bool(re.search(r"^- \[", content, re.MULTILINE) or re.search(r"^\d+\.", content, re.MULTILINE))
    has_install = any(kw in content_lower for kw in ["pip install", "pip upgrade", "upgrade"])
    if has_checklist or has_install:
        print("PASS: Has migration checklist or upgrade command")
        score += 1
    else:
        print("FAIL: Missing migration checklist or upgrade command")
        missed.append("migration checklist or upgrade command")

    print(f"\nScore: {score}/{max_score}")
    if score >= 7:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 5:
        missing_str = "; ".join(missed) if missed else "n/a"
        print(
            f"WARN: Score {score}/{max_score} — need ≥7 for EXCELLENT. "
            f"Missing: {missing_str}"
        )
        print("VERIFICATION_RESULT: PASS")
    else:
        print(f"FAIL: Score too low ({score}/{max_score})")
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
