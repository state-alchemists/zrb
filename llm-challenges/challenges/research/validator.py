"""Validator for the architecture-decision-record (research) challenge."""

from __future__ import annotations

from pathlib import Path

from zrb_llm_evaluator.models import ValidationCheck, ValidationResult
from zrb_llm_evaluator.protocols import ValidatorProtocol

MAX_SCORE = 8
SKIP_FILES = {"readme.md", "system_context.md"}


def _find_adr_file(output_dir: Path) -> Path | None:
    primary = output_dir / "ADR-001-notification-architecture.md"
    if primary.is_file():
        return primary
    candidates = sorted(
        entry
        for entry in output_dir.iterdir()
        if entry.suffix.lower() == ".md" and entry.name.lower() not in SKIP_FILES
    )
    return candidates[0] if candidates else None


class ResearchValidator:
    def validate(self, output_dir: Path, log_content: str) -> ValidationResult:
        details: list[ValidationCheck] = []
        adr = _find_adr_file(output_dir)
        if adr is None:
            details.append(
                ValidationCheck(
                    name="adr_file",
                    passed=False,
                    message="No ADR markdown file found",
                )
            )
            return ValidationResult(status="FAIL", score=0.0, details=details)

        details.append(
            ValidationCheck(
                name="adr_file",
                passed=True,
                message=f"Using {adr.name}",
            )
        )

        content = adr.read_text(encoding="utf-8")
        lower = content.lower()
        score = 0

        words = len(content.split())
        long_enough = words >= 500
        score += int(long_enough)
        details.append(
            ValidationCheck(
                name="substantial_content",
                passed=long_enough,
                message=f"{words} words (need ≥500)",
            )
        )

        required_sections = ("context", "decision", "consequences", "alternatives")
        found = [s for s in required_sections if s in lower]
        sections_ok = len(found) >= 3
        score += int(sections_ok)
        missing_sections = [s for s in required_sections if s not in lower]
        details.append(
            ValidationCheck(
                name="adr_sections",
                passed=sections_ok,
                message=f"found={found}"
                + (f", missing={missing_sections}" if missing_sections else ""),
            )
        )

        status_ok = "status" in lower and any(
            s in lower for s in ("proposed", "accepted", "draft")
        )
        score += int(status_ok)
        details.append(
            ValidationCheck(
                name="status_field",
                passed=status_ok,
                message="Status field present"
                if status_ok
                else "Missing Status field (Proposed/Accepted/Draft)",
            )
        )

        has_kafka = "kafka" in lower
        has_redis = "redis" in lower
        both_ok = has_kafka and has_redis
        score += int(both_ok)
        details.append(
            ValidationCheck(
                name="evaluates_both_options",
                passed=both_ok,
                message=f"kafka={has_kafka}, redis={has_redis}",
            )
        )

        decision_terms = (
            "we will use",
            "we choose",
            "we adopt",
            "decision:",
            "chosen:",
            "recommend",
        )
        has_decision = any(t in lower for t in decision_terms)
        recommendation_ok = has_decision or both_ok
        score += int(recommendation_ok)
        details.append(
            ValidationCheck(
                name="clear_recommendation",
                passed=recommendation_ok,
                message="Recommendation present"
                if recommendation_ok
                else "No definitive recommendation found",
            )
        )

        tech_terms = (
            "throughput",
            "ordering",
            "retention",
            "consumer group",
            "exactly-once",
            "at-least-once",
            "operational",
            "replication",
            "partition",
            "stream",
            "durability",
            "latency",
        )
        covered_tech = [t for t in tech_terms if t in lower]
        tech_ok = len(covered_tech) >= 4
        score += int(tech_ok)
        details.append(
            ValidationCheck(
                name="technical_properties",
                passed=tech_ok,
                message=f"covered {len(covered_tech)}/12 ({', '.join(covered_tech[:4])}...)",
            )
        )

        constraint_terms = (
            "team",
            "engineer",
            "redis",
            "operational complexity",
            "experience",
            "budget",
            "migration",
        )
        covered_constraints = [t for t in constraint_terms if t in lower]
        constraints_ok = len(covered_constraints) >= 3
        score += int(constraints_ok)
        details.append(
            ValidationCheck(
                name="constraint_context",
                passed=constraints_ok,
                message=f"covered {len(covered_constraints)} constraint terms",
            )
        )

        has_pros = any(t in lower for t in ("pro", "advantage", "benefit", "positive"))
        has_cons = any(
            t in lower
            for t in ("con", "disadvantage", "downside", "risk", "negative")
        )
        pros_cons_ok = has_pros and has_cons
        score += int(pros_cons_ok)
        details.append(
            ValidationCheck(
                name="pros_and_cons",
                passed=pros_cons_ok,
                message=f"pros={has_pros}, cons={has_cons}",
            )
        )

        normalized = score / MAX_SCORE
        if score >= 7:
            status = "EXCELLENT"
        elif score >= 5:
            status = "PASS"
        else:
            status = "FAIL"
        return ValidationResult(status=status, score=normalized, details=details)


validator = ResearchValidator()
