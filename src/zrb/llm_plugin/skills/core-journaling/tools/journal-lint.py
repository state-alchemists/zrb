#!/usr/bin/env python3
"""Validate a zrb journal against the graph protocol.

Checks (from core-journaling/SKILL.md):
  - BIDIRECTIONAL  — every forward link has a corresponding backlink in the target
  - NO ORPHANS     — every file is reachable from index.md via forward links
  - INDEX COVERAGE — every non-leaf directory has an index.md
  - PATH HEALTH    — no broken internal links (link target exists)

Usage:
  python journal-lint.py <journal-root>            # human-readable output
  python journal-lint.py <journal-root> --json     # machine-readable output

Exit code is 0 if clean, 1 if any issue found, 2 on internal error.

Stdlib-only. No external dependencies.

Notes on the activity-log subtree:
  - Date-leaf directories (activity-log/YYYY/YYYY-MM/) do NOT require their own
    index.md — their parent month index covers them. The linter skips index
    requirements there.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BACKLINK_HEADER_RE = re.compile(r"^##\s+Backlinks\s*$", re.MULTILINE)


@dataclass
class JournalIssue:
    kind: str  # one of: broken-link, missing-backlink, orphan, missing-index
    path: str  # file (or directory) where the issue surfaces
    detail: str

    def format(self) -> str:
        return f"[{self.kind}] {self.path}: {self.detail}"


@dataclass
class LintReport:
    journal_root: str
    issues: list[JournalIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "journal_root": self.journal_root,
            "issue_count": len(self.issues),
            "issues": [
                {"kind": i.kind, "path": i.path, "detail": i.detail}
                for i in self.issues
            ],
        }


def _is_internal(target: str) -> bool:
    """Heuristic: anything not starting with http(s):// or mailto: is internal."""
    return not re.match(r"^(https?|mailto):", target)


def _normalize_target(file_path: Path, root: Path, target: str) -> Path | None:
    """Resolve a markdown link target to an absolute path within the journal.

    Assumes root and file_path are already resolved (real paths).
    """
    target = target.split("#", 1)[0].strip()  # strip anchor
    if not target:
        return None
    candidate = (file_path.parent / target).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None  # link points outside the journal — ignore
    return candidate


def _is_date_leaf_dir(path: Path, root: Path) -> bool:
    """activity-log/YYYY/YYYY-MM dirs are exempt from the index requirement."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    parts = rel.parts
    return (
        len(parts) >= 3
        and parts[0] == "activity-log"
        and re.fullmatch(r"\d{4}", parts[1] or "")
        and re.fullmatch(r"\d{4}-\d{2}", parts[2] or "")
        and len(parts) == 3
    )


def lint(root: Path) -> LintReport:
    if not root.is_dir():
        report = LintReport(journal_root=str(root))
        report.issues.append(
            JournalIssue("broken-link", str(root), "journal root is not a directory")
        )
        return report

    # Resolve once so all subsequent path operations agree (handles /tmp -> /private/tmp etc.)
    root = root.resolve()
    report = LintReport(journal_root=str(root))

    md_files = [p.resolve() for p in root.rglob("*.md") if p.is_file()]
    if not md_files:
        return report  # empty journal is valid

    # Index of forward links: source_file -> set of target_files
    forward: dict[Path, set[Path]] = defaultdict(set)
    # Index of backlink targets: target_file -> set of files that backlink to it
    backlink_sources: dict[Path, set[Path]] = defaultdict(set)

    for f in md_files:
        try:
            content = f.read_text(encoding="utf-8")
        except OSError as e:
            report.issues.append(
                JournalIssue("broken-link", str(f), f"unreadable: {e}")
            )
            continue

        # Split body vs Backlinks section
        backlink_match = BACKLINK_HEADER_RE.search(content)
        body = content[: backlink_match.start()] if backlink_match else content
        backlink_section = content[backlink_match.end() :] if backlink_match else ""

        # Forward links: in body only (links in the Backlinks section are the reverse direction)
        for _, target in LINK_RE.findall(body):
            if not _is_internal(target):
                continue
            resolved = _normalize_target(f, root, target)
            if resolved is None:
                continue
            if not resolved.exists():
                report.issues.append(
                    JournalIssue(
                        "broken-link",
                        str(f.relative_to(root)),
                        f"-> {target} (target missing)",
                    )
                )
                continue
            forward[f].add(resolved)

        # Backlinks: in the Backlinks section only
        for _, target in LINK_RE.findall(backlink_section):
            if not _is_internal(target):
                continue
            resolved = _normalize_target(f, root, target)
            if resolved is None or not resolved.exists():
                continue
            backlink_sources[f].add(resolved)

    # Check 1: bidirectional links
    for src, targets in forward.items():
        for tgt in targets:
            if src not in backlink_sources.get(tgt, set()):
                # index.md files are exempt from needing backlinks
                if tgt.name == "index.md":
                    continue
                report.issues.append(
                    JournalIssue(
                        "missing-backlink",
                        str(tgt.relative_to(root)),
                        f"no backlink to {src.relative_to(root)}",
                    )
                )

    # Check 2: orphans (files unreachable from root index.md via forward links)
    root_index = root / "index.md"
    if root_index.exists():
        reachable: set[Path] = set()
        frontier = [root_index]
        while frontier:
            current = frontier.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for tgt in forward.get(current, set()):
                if tgt not in reachable:
                    frontier.append(tgt)

        for f in md_files:
            if f not in reachable and f != root_index:
                # date-day files under activity-log are commonly reachable only via month index;
                # if the month index links them, they're reachable. If not, they're orphans.
                report.issues.append(
                    JournalIssue(
                        "orphan",
                        str(f.relative_to(root)),
                        "unreachable from root index.md",
                    )
                )
    else:
        report.issues.append(
            JournalIssue("missing-index", "index.md", "journal root index.md missing")
        )

    # Check 3: directory index coverage
    seen_dirs: set[Path] = set()
    for f in md_files:
        seen_dirs.add(f.parent)
    for d in seen_dirs:
        if d == root:
            continue
        if _is_date_leaf_dir(d, root):
            continue
        if not (d / "index.md").exists():
            report.issues.append(
                JournalIssue(
                    "missing-index",
                    str(d.relative_to(root)),
                    "directory has notes but no index.md",
                )
            )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("journal_root", help="Path to the journal root directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    root = Path(args.journal_root)
    try:
        report = lint(root)
    except Exception as e:  # noqa: BLE001
        print(f"internal error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        if not report.issues:
            print(f"OK — journal at {root} is clean")
        else:
            print(f"{len(report.issues)} issue(s) in journal at {root}:")
            for issue in report.issues:
                print(f"  {issue.format()}")

    return 0 if not report.issues else 1


if __name__ == "__main__":
    sys.exit(main())
