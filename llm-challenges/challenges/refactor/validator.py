"""Validator for the pipeline refactor challenge.

Mirrors the original verify.py: static checks for env-var/SQL/regex/etc.
plus a subprocess execution of the refactored script that must regenerate
report.html with the expected sections and source-derived data points.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from zrb_llm_evaluator.models import ValidationCheck, ValidationResult
from zrb_llm_evaluator.protocols import ValidatorProtocol

MAX_SCORE = 8

LOG_FIXTURE = (
    "2024-01-01 12:00:00 INFO User 42 logged in\n"
    "2024-01-01 12:05:00 ERROR Database timeout\n"
    "2024-01-01 12:05:05 ERROR Database timeout\n"
    "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
    "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
    "2024-01-01 12:10:00 INFO User 42 logged out\n"
)


def _find_refactor_file(output_dir: Path) -> Path | None:
    for candidate in ("pipeline_refactored.py", "pipeline.py"):
        path = output_dir / candidate
        if path.is_file():
            return path
    for entry in sorted(output_dir.iterdir()):
        if entry.suffix == ".py" and entry.name != "validator.py":
            return entry
    return None


class RefactorValidator:
    def validate(self, output_dir: Path, log_content: str) -> ValidationResult:
        details: list[ValidationCheck] = []
        refactor_file = _find_refactor_file(output_dir)
        if refactor_file is None:
            details.append(
                ValidationCheck(
                    name="refactor_file",
                    passed=False,
                    message="No refactored .py script found",
                )
            )
            return ValidationResult(status="FAIL", score=0.0, details=details)

        details.append(
            ValidationCheck(
                name="refactor_file",
                passed=True,
                message=f"Checking {refactor_file.name}",
            )
        )

        content = refactor_file.read_text(encoding="utf-8")
        content_lower = content.lower()
        score = 0
        critical_ok = True

        env_ok = "os.getenv" in content or "os.environ" in content
        score += int(env_ok)
        details.append(
            ValidationCheck(
                name="env_var_config",
                passed=env_ok,
                message="Env-var config present" if env_ok else "No os.getenv/os.environ usage",
            )
        )

        leaked_credential = "password123" in content
        if leaked_credential:
            critical_ok = False
        details.append(
            ValidationCheck(
                name="no_hardcoded_credential",
                passed=not leaked_credential,
                message="Hardcoded 'password123' still present" if leaked_credential
                else "No hardcoded credential",
            )
        )

        sql_lines = [l for l in content.split("\n") if "execute(" in l.lower()]
        injection_patterns = (
            r"execute\s*\(.*%[sdf]",
            r"execute\s*\(.*\+",
            r"execute\s*\(f[\"']",
        )
        has_injection = any(
            re.search(pat, line) for line in sql_lines for pat in injection_patterns
        )
        if not sql_lines:
            score += 1
            details.append(
                ValidationCheck(
                    name="sql_injection_check",
                    passed=True,
                    message="No execute() calls — skipped",
                )
            )
        elif not has_injection:
            score += 1
            details.append(
                ValidationCheck(
                    name="sql_injection_check",
                    passed=True,
                    message="SQL queries appear parameterized",
                )
            )
        else:
            critical_ok = False
            details.append(
                ValidationCheck(
                    name="sql_injection_check",
                    passed=False,
                    message="execute() call uses string interpolation",
                )
            )

        has_extract = "extract" in content_lower
        has_transform = "transform" in content_lower
        has_load = "load" in content_lower or "report" in content_lower
        etl_ok = has_extract and has_transform and has_load
        score += int(etl_ok)
        details.append(
            ValidationCheck(
                name="etl_pattern",
                passed=etl_ok,
                message=f"extract={has_extract}, transform={has_transform}, load={has_load}",
            )
        )

        fn_count = len(re.findall(r"^def\s+\w+", content, re.MULTILINE))
        class_count = len(re.findall(r"^class\s+\w+", content, re.MULTILINE))
        separation_ok = fn_count >= 3 or class_count >= 1
        score += int(separation_ok)
        details.append(
            ValidationCheck(
                name="separation_of_concerns",
                passed=separation_ok,
                message=f"{fn_count} function(s), {class_count} class(es)",
            )
        )

        regex_ok = "import re" in content or bool(
            re.search(r"\bre\.(search|match|findall|compile)", content)
        )
        score += int(regex_ok)
        details.append(
            ValidationCheck(
                name="regex_parsing",
                passed=regex_ok,
                message="Uses re module" if regex_ok else "No regex usage detected",
            )
        )

        has_types = bool(
            re.search(r"->\s*\w|\:\s*(str|int|float|List|Dict|Optional|bool)", content)
        )
        has_docs = '"""' in content or "'''" in content
        annotations_ok = has_types and has_docs
        score += int(annotations_ok)
        details.append(
            ValidationCheck(
                name="type_hints_and_docstrings",
                passed=annotations_ok,
                message=f"types={has_types}, docstrings={has_docs}",
            )
        )

        # Run the refactored script against a fixed log fixture.
        log_path = output_dir / "server.log"
        log_path.write_text(LOG_FIXTURE, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, refactor_file.name],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(output_dir),
                env={
                    **os.environ,
                    "LOG_FILE": "server.log",
                    "DB_PATH": "metrics.db",
                    "DB_HOST": "localhost",
                    "DB_PORT": "5432",
                    "DB_USER": "admin",
                    "DB_PASS": "password123",
                },
            )
            if result.returncode == 0:
                score += 1
                details.append(
                    ValidationCheck(
                        name="script_runs",
                        passed=True,
                        message="Script exited 0",
                    )
                )
            else:
                critical_ok = False
                details.append(
                    ValidationCheck(
                        name="script_runs",
                        passed=False,
                        message=f"exit={result.returncode}: {result.stderr[:400]}",
                    )
                )
        except Exception as exc:
            critical_ok = False
            details.append(
                ValidationCheck(
                    name="script_runs",
                    passed=False,
                    message=f"Execution error: {exc}",
                )
            )

        report = output_dir / "report.html"
        if report.is_file():
            html = report.read_text(encoding="utf-8").lower()
            has_errors_section = "error" in html
            has_latency_section = "latency" in html or "api" in html
            has_sessions_section = "session" in html
            section_ok = has_errors_section and has_latency_section and has_sessions_section
            expected_data = (
                ("database timeout", "error message"),
                ("/users/profile", "API endpoint"),
                ("250", "API latency value"),
            )
            missing = [label for needle, label in expected_data if needle not in html]
            if section_ok and not missing:
                score += 1
                details.append(
                    ValidationCheck(
                        name="report_html",
                        passed=True,
                        message="Sections present and source data preserved",
                    )
                )
            else:
                critical_ok = False
                detail_msg = []
                if not section_ok:
                    detail_msg.append(
                        f"sections — errors={has_errors_section}, "
                        f"latency={has_latency_section}, sessions={has_sessions_section}"
                    )
                if missing:
                    detail_msg.append(f"missing data: {', '.join(missing)}")
                details.append(
                    ValidationCheck(
                        name="report_html",
                        passed=False,
                        message="; ".join(detail_msg),
                    )
                )
        else:
            critical_ok = False
            details.append(
                ValidationCheck(
                    name="report_html",
                    passed=False,
                    message="report.html not generated",
                )
            )

        normalized = score / MAX_SCORE
        if not critical_ok:
            return ValidationResult(status="FAIL", score=normalized, details=details)
        if score >= 7:
            status = "EXCELLENT"
        elif score >= 5:
            status = "PASS"
        else:
            status = "FAIL"
        return ValidationResult(status=status, score=normalized, details=details)


validator = RefactorValidator()
