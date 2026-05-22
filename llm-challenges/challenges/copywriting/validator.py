"""Validator for the copywriting (v1→v2 migration guide) challenge."""

from __future__ import annotations

import re
from pathlib import Path

from zrb_llm_evaluator.models import ValidationCheck, ValidationResult
from zrb_llm_evaluator.protocols import ValidatorProtocol

MAX_SCORE = 8


def _find_migration_file(output_dir: Path) -> Path | None:
    primary = output_dir / "MIGRATION.md"
    if primary.is_file():
        return primary
    for entry in output_dir.iterdir():
        if entry.suffix.lower() == ".md" and "migration" in entry.name.lower():
            return entry
    return None


class CopywritingValidator:
    def validate(self, output_dir: Path, log_content: str) -> ValidationResult:
        details: list[ValidationCheck] = []
        migration = _find_migration_file(output_dir)
        if migration is None:
            details.append(
                ValidationCheck(
                    name="migration_file",
                    passed=False,
                    message="MIGRATION.md not found",
                )
            )
            return ValidationResult(status="FAIL", score=0.0, details=details)

        details.append(
            ValidationCheck(
                name="migration_file",
                passed=True,
                message=f"Using {migration.name}",
            )
        )

        content = migration.read_text(encoding="utf-8")
        content_lower = content.lower()
        score = 0

        has_heading = bool(re.search(r"^#{1,3} ", content, re.MULTILINE))
        score += int(has_heading)
        details.append(
            ValidationCheck(
                name="markdown_headings",
                passed=has_heading,
                message="Has markdown headings" if has_heading else "No markdown headings",
            )
        )

        word_count = len(content.split())
        long_enough = word_count >= 400
        score += int(long_enough)
        details.append(
            ValidationCheck(
                name="substantial_content",
                passed=long_enough,
                message=f"{word_count} words (need ≥400)",
            )
        )

        fences = len(re.findall(r"```", content))
        enough_blocks = fences >= 6
        score += int(enough_blocks)
        details.append(
            ValidationCheck(
                name="code_blocks",
                passed=enough_blocks,
                message=f"{fences // 2} fenced code block(s) (need ≥3)",
            )
        )

        auth_ok = "authorization" in content_lower and "bearer" in content_lower
        score += int(auth_ok)
        details.append(
            ValidationCheck(
                name="auth_header_change",
                passed=auth_ok,
                message="Authorization: Bearer documented"
                if auth_ok
                else "Missing Authorization/Bearer reference",
            )
        )

        uuid_ok = "uuid" in content_lower
        score += int(uuid_ok)
        details.append(
            ValidationCheck(
                name="uuid_id_change",
                passed=uuid_ok,
                message="UUID id change documented" if uuid_ok else "UUID change not mentioned",
            )
        )

        rename_ok = "completed" in content_lower and (
            "done" in content_lower or "renamed" in content_lower
        )
        score += int(rename_ok)
        details.append(
            ValidationCheck(
                name="field_rename",
                passed=rename_ok,
                message="done→completed rename documented"
                if rename_ok
                else "Missing done→completed rename",
            )
        )

        project_ok = "project_id" in content_lower and "/v2" in content_lower
        score += int(project_ok)
        details.append(
            ValidationCheck(
                name="project_id_and_v2_prefix",
                passed=project_ok,
                message="project_id + /v2/ prefix covered"
                if project_ok
                else "Missing project_id or /v2/ prefix",
            )
        )

        has_checklist = bool(
            re.search(r"^- \[", content, re.MULTILINE)
            or re.search(r"^\d+\.", content, re.MULTILINE)
        )
        has_upgrade = any(
            kw in content_lower for kw in ("pip install", "pip upgrade", "upgrade")
        )
        finish_ok = has_checklist or has_upgrade
        score += int(finish_ok)
        details.append(
            ValidationCheck(
                name="checklist_or_upgrade",
                passed=finish_ok,
                message="Checklist or upgrade command present"
                if finish_ok
                else "Missing checklist and upgrade command",
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


validator = CopywritingValidator()
