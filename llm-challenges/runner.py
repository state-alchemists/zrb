#!/usr/bin/env python3
"""LLM challenge harness.

Runs each challenge against each requested model via the ``zrb chat`` CLI,
executes the challenge's verify script, and writes a Markdown report plus
a JSON result cache that can be resumed across runs.

Layout:
- Config + dataclasses
- Log parsing (tool calls, token usage)
- Subprocess orchestration (zrb chat + verify.sh/verify.py)
- Status classification
- Report rendering
- main()
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHALLENGES_DIR = Path("challenges")
EXPERIMENT_BASE_DIR = Path("experiment")
DEFAULT_MODELS: List[str] = [""]
DEFAULT_TIMEOUT = 300  # 5 min per challenge
VERIFY_TIMEOUT = 60
TOOL_CALL_EMOJI = "🧰"
COST_LINE_EMOJI = "💸"
ZRB_ENV_OVERRIDES = {
    "ZRB_LLM_SHOW_TOOL_CALL_RESULT": "true",
    "ZRB_LLM_SHOW_TOOL_CALL_DETAIL": "true",
    "ZRB_LLM_INCLUDE_SECTIONS": (
        "persona,mandate,git_mandate,system_context,tool_guidance,claude_skills"
    ),
}

# Status constants — single source of truth for the strings used in
# ChallengeResult.status, the report icon map, and the resume-skip logic.
STATUS_EXCELLENT = "EXCELLENT"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_ERROR = "ERROR"
STATUS_EXECUTION_COMPLETE = "EXECUTION_COMPLETE"
STATUS_EXECUTION_FAILED = "EXECUTION_FAILED"
STATUS_VERIFY_FAILED = "VERIFY_FAILED"  # legacy alias preserved in icon map
STATUS_SUCCESS = "SUCCESS"  # legacy alias preserved in skip set

# Anything in this set is a deterministic outcome and will not be retried
# on a resumed run.
TERMINAL_STATUSES = frozenset(
    {STATUS_PASS, STATUS_EXCELLENT, STATUS_SUCCESS, STATUS_FAIL}
)

STATUS_ICONS = {
    STATUS_EXCELLENT: "🌟",
    STATUS_PASS: "✅",
    STATUS_FAIL: "❌",
    STATUS_VERIFY_FAILED: "❌",
    STATUS_TIMEOUT: "⏱️",
    STATUS_EXECUTION_FAILED: "💥",
    STATUS_ERROR: "💥",
}
DEFAULT_STATUS_ICON = "❓"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ChallengeResult:
    challenge_name: str
    model: str
    status: str
    duration: float
    tool_calls: List[str]
    tool_call_count: int
    exit_code: int
    log_path: str
    workdir: str
    verification_output: Optional[str] = None
    # Token-usage fields — zero when the cost summary line was missing
    # (older runs / aborted runs / non-LLM exits).
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class ExperimentConfig:
    models: List[str]
    parallelism: int
    timeout: int
    filter: Optional[str] = None
    verbose: bool = False


def parse_args() -> ExperimentConfig:
    parser = argparse.ArgumentParser(description="Run LLM Challenges")
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help=(
            "Models to test (e.g., google-gla:gemini-2.5-flash "
            "openai:gpt-4o deepseek:deepseek-chat)"
        ),
    )
    parser.add_argument(
        "--parallelism", type=int, default=4,
        help="Number of concurrent experiments",
    )
    parser.add_argument(
        "--filter", type=str, default=None,
        help="Filter challenges by name (comma-separated)",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="Timeout per challenge in seconds",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show verbose output",
    )
    args = parser.parse_args()
    return ExperimentConfig(
        models=args.models,
        parallelism=args.parallelism,
        timeout=args.timeout,
        filter=args.filter,
        verbose=args.verbose,
    )


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------


def extract_tool_calls(log_content: str) -> List[str]:
    """Extract tool-call names from a zrb chat log.

    Tries patterns in priority order; the first that matches wins.
    """
    patterns = (
        rf"{TOOL_CALL_EMOJI}\s+\w+\s+\|\s+(\w+)",
        rf"{TOOL_CALL_EMOJI}[^|]+\|\s*(\w+)",
        r"Tool call: (\w+)",
        r"tool='(\w+)'",
    )
    for pat in patterns:
        matches = re.findall(pat, log_content)
        if matches:
            return matches
    return []


def count_tool_calls(log_content: str) -> int:
    """Count tool calls by tally of the tool emoji."""
    return log_content.count(TOOL_CALL_EMOJI)


def extract_token_usage(log_content: str) -> Dict[str, int]:
    """Parse the cumulative cost summary line zrb emits at session end.

    Line shape:
        💸 (Requests: 21 | Tool Calls: 37 | Total: 478790) Input: 472682 |
           Audio Input: 0 | Output: 6108 | ... | Cache Read: 412672 | ...

    Missing line yields zeros for all fields. Uses the last cost line in
    case more than one is present.
    """
    fields = {
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
    }
    if COST_LINE_EMOJI not in log_content:
        return fields
    last_line = ""
    for line in log_content.splitlines():
        if COST_LINE_EMOJI in line:
            last_line = line
    if not last_line:
        return fields
    patterns = {
        "total_tokens": r"Total:\s*(\d+)",
        "input_tokens": r"\bInput:\s*(\d+)",
        "output_tokens": r"\bOutput:\s*(\d+)",
        "cache_read_tokens": r"Cache Read:\s*(\d+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, last_line)
        if m:
            fields[key] = int(m.group(1))
    return fields


def sanitize_model_name_for_path(model: str) -> str:
    """Folder-safe form of a model name (replaces ':' with '-')."""
    return model.replace(":", "-")


# ---------------------------------------------------------------------------
# Subprocess orchestration
# ---------------------------------------------------------------------------


def _prepare_experiment_dir(challenge_path: Path, model: str) -> Tuple[Path, Path]:
    """Create a fresh ``exp_dir`` and copy challenge ``workdir/`` into it.

    Returns ``(exp_dir, workdir)``. Only the ``workdir/`` subtree is
    copied so the agent can't see verify.py / instruction.md.
    """
    model_safe = sanitize_model_name_for_path(model)
    exp_dir = EXPERIMENT_BASE_DIR / model_safe / challenge_path.name
    if exp_dir.exists():
        shutil.rmtree(exp_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)
    workdir = exp_dir / "workdir"
    shutil.copytree(challenge_path / "workdir", workdir, dirs_exist_ok=True)
    return exp_dir, workdir


def _build_zrb_env(exp_dir: Path) -> Dict[str, str]:
    """Compose the env for the zrb subprocess.

    ``GIT_CEILING_DIRECTORIES`` is pinned to the experiment dir so the
    agent doesn't discover the parent repo.
    """
    env = os.environ.copy()
    env.update(ZRB_ENV_OVERRIDES)
    env["GIT_CEILING_DIRECTORIES"] = str(exp_dir.resolve())
    return env


def _build_zrb_cmd(model: str, instruction: str) -> List[str]:
    return [
        "zrb", "chat",
        "--model", model,
        "--interactive", "false",
        "--yolo", "true",
        "--message", instruction,
    ]


def _run_zrb_subprocess(
    cmd: List[str],
    env: Dict[str, str],
    workdir: Path,
    log_file: Path,
    timeout: int,
    verbose: bool,
    model: str,
) -> Tuple[int, str]:
    """Run zrb chat, capturing stdout+stderr to ``log_file``.

    Returns ``(exit_code, exec_status)`` where ``exec_status`` is one of
    ``EXECUTION_COMPLETE``, ``EXECUTION_FAILED``, ``TIMEOUT``, ``ERROR``.
    """
    try:
        if verbose:
            print(f"{model} Running command...")
            with open(log_file, "w", encoding="utf-8") as f:
                proc = subprocess.Popen(
                    cmd, cwd=workdir,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env=env, text=True, bufsize=1, universal_newlines=True,
                )
                # Drain stdout in a thread so we can enforce ``timeout`` on
                # the process itself via ``wait``. The naive ``for line in
                # proc.stdout`` blocks until the child closes stdout, which
                # only happens at exit — so ``wait(timeout=...)`` after it
                # would never actually fire.
                def _drain() -> None:
                    for line in proc.stdout:
                        f.write(line)
                        if TOOL_CALL_EMOJI in line:
                            print(
                                f"  {model} Tool call detected: "
                                f"{line.strip()[:100]}..."
                            )

                drainer = threading.Thread(target=_drain, daemon=True)
                drainer.start()
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    drainer.join(timeout=5)
                    raise
                drainer.join(timeout=5)
                exit_code = proc.returncode
        else:
            with open(log_file, "w") as f:
                proc = subprocess.run(
                    cmd, cwd=workdir,
                    stdout=f, stderr=subprocess.STDOUT,
                    timeout=timeout, env=env,
                )
                exit_code = proc.returncode
        exec_status = (
            STATUS_EXECUTION_COMPLETE if exit_code == 0
            else STATUS_EXECUTION_FAILED
        )
        return exit_code, exec_status
    except subprocess.TimeoutExpired:
        with open(log_file, "a") as f:
            f.write(f"\n[Runner] Timeout of {timeout}s exceeded.\n")
        if verbose:
            print(f"❌ {model} Timeout after {timeout}s")
        return 124, STATUS_TIMEOUT
    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"\n[Runner] Exception: {e}\n")
        if verbose:
            print(f"❌ {model} Error: {e}")
        return -1, STATUS_ERROR


def run_verification(challenge_dir: Path, workdir: Path) -> Tuple[int, str]:
    """Copy and run verify.sh or verify.py for this challenge.

    Returns ``(exit_code, combined_output)``. If neither verify script
    exists, returns ``(0, "")``.
    """
    src_sh = challenge_dir / "verify.sh"
    src_py = challenge_dir / "verify.py"
    dst_sh = workdir / "verify.sh"
    dst_py = workdir / "verify.py"
    if src_sh.exists():
        shutil.copy2(src_sh, dst_sh)
    if src_py.exists():
        shutil.copy2(src_py, dst_py)

    if dst_sh.exists():
        return _run_subprocess_safely(
            ["bash", "./verify.sh"], workdir, make_executable=dst_sh,
        )
    if dst_py.exists():
        return _run_subprocess_safely(
            ["python3", "verify.py"], workdir,
        )
    return 0, ""


def _run_subprocess_safely(
    cmd: List[str], cwd: Path, make_executable: Optional[Path] = None,
) -> Tuple[int, str]:
    """Run a verify script, returning ``(exit_code, stdout+stderr)``.

    Any exception is captured as a -1 exit + the exception message.
    """
    try:
        if make_executable is not None:
            make_executable.chmod(make_executable.stat().st_mode | 0o111)
        res = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=VERIFY_TIMEOUT,
        )
        return res.returncode, (res.stdout or "") + "\n" + (res.stderr or "")
    except Exception as e:
        return -1, str(e)


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------


def _classify_final_status(
    exec_status: str, verify_code: int, verify_output: str,
) -> str:
    """Combine execution outcome + verifier output into a final status.

    Verifier-emitted ``VERIFICATION_RESULT:`` markers take precedence
    over execution status — a model may produce correct output but exit
    nonzero due to an unrelated framework error. Legacy verify scripts
    without markers fall back to verify exit code.
    """
    if "VERIFICATION_RESULT: EXCELLENT" in verify_output:
        return STATUS_EXCELLENT
    if "VERIFICATION_RESULT: PASS" in verify_output:
        return STATUS_PASS
    if "VERIFICATION_RESULT: FAIL" in verify_output:
        return STATUS_FAIL
    if exec_status == STATUS_EXECUTION_COMPLETE:
        return STATUS_PASS if verify_code == 0 else STATUS_FAIL
    return exec_status


# ---------------------------------------------------------------------------
# Single-experiment driver
# ---------------------------------------------------------------------------


def run_single_experiment(
    challenge_path: Path, model: str, timeout: int, verbose: bool = False,
) -> ChallengeResult:
    """Run one (model, challenge) cell end-to-end."""
    challenge_name = challenge_path.name
    if verbose:
        banner = "=" * 60
        print(f"\n{banner}\nTesting {model} on {challenge_name} challenge\n{banner}")

    exp_dir, workdir = _prepare_experiment_dir(challenge_path, model)

    instruction_file = challenge_path / "instruction.md"
    if not instruction_file.exists():
        if verbose:
            print(f"ERROR: {instruction_file} not found")
        return ChallengeResult(
            challenge_name=challenge_name,
            model=model,
            status=STATUS_ERROR,
            duration=0,
            tool_calls=[],
            tool_call_count=0,
            exit_code=-1,
            log_path="",
            workdir=str(workdir),
            verification_output="Missing instruction.md",
        )

    instruction = instruction_file.read_text().strip()
    if verbose:
        print(f"Instruction: {instruction[:100]}...")

    env = _build_zrb_env(exp_dir)
    cmd = _build_zrb_cmd(model, instruction)
    log_file = exp_dir / "combined.log"

    if verbose:
        print(f"Command: {' '.join(cmd[:4])} [message hidden]")
        print(f"Timeout: {timeout}s")

    start = time.time()
    exit_code, exec_status = _run_zrb_subprocess(
        cmd, env, workdir, log_file, timeout, verbose, model,
    )
    duration = time.time() - start

    log_content = log_file.read_text() if log_file.exists() else ""
    tool_calls = extract_tool_calls(log_content)
    tool_call_count = count_tool_calls(log_content)
    token_usage = extract_token_usage(log_content)

    if verbose:
        print(f"\n{model} Result after {duration:.1f}s:")
        print(f"{model} Exit code: {exit_code}")
        if tool_call_count > 0:
            print(f"✅ Tool calls detected: {tool_call_count}")
            if tool_calls:
                shown = ", ".join(tool_calls[:5])
                suffix = "..." if len(tool_calls) > 5 else ""
                print(f"{model} Tools used: {shown}{suffix}")
        else:
            print("⚠️ No tool calls detected")

    verify_code, verify_output = run_verification(challenge_path, workdir)
    final_status = _classify_final_status(exec_status, verify_code, verify_output)

    if verbose:
        print(f"Final Status: {final_status}")
        if verify_code != 0:
            print(f"⚠️ {model} Verification script exit code: {verify_code}")

    return ChallengeResult(
        challenge_name=challenge_name,
        model=model,
        status=final_status,
        duration=duration,
        tool_calls=tool_calls,
        tool_call_count=tool_call_count,
        exit_code=exit_code,
        log_path=str(log_file),
        workdir=str(workdir),
        verification_output=verify_output or None,
        total_tokens=token_usage["total_tokens"],
        input_tokens=token_usage["input_tokens"],
        output_tokens=token_usage["output_tokens"],
        cache_read_tokens=token_usage["cache_read_tokens"],
    )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def generate_report(results: List[ChallengeResult], output_file: Path) -> None:
    per_challenge_best = _compute_per_challenge_best(results)
    with open(output_file, "w") as f:
        _write_header(f)
        _write_summary_table(f, results, per_challenge_best)
        _write_detail_section(f, results)


def _write_header(f) -> None:
    f.write("# LLM Challenge Experiment Report\n\n")
    f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(
        "_Bold cells mark the best (lowest) value for that challenge among "
        "EXCELLENT runs — fastest, fewest tool calls, fewest tokens._\n\n"
    )


def _write_summary_table(
    f, results: List[ChallengeResult],
    per_challenge_best: Dict[str, Dict[str, Optional[float]]],
) -> None:
    f.write("| Model | Challenge | Status | Time (s) | Tools | Tokens | Verify |\n")
    f.write("|---|---|---|---|---|---|---|\n")
    for r in results:
        best = per_challenge_best.get(r.challenge_name, {})
        f.write(_render_summary_row(r, best) + "\n")


def _render_summary_row(
    r: ChallengeResult, best: Dict[str, Optional[float]],
) -> str:
    verify_icon = STATUS_ICONS.get(r.status, DEFAULT_STATUS_ICON)
    verify_note = _summarize_verification(r.verification_output, r.status)
    verify_cell = f"{verify_icon} {verify_note}" if verify_note else verify_icon

    eligible = r.status == STATUS_EXCELLENT
    time_cell = _maybe_bold(
        f"{r.duration:.2f}",
        eligible
        and best.get("duration") is not None
        and r.duration == best["duration"],
    )
    tools_cell = _maybe_bold(
        str(r.tool_call_count),
        eligible
        and best.get("tools") is not None
        and r.tool_call_count > 0
        and r.tool_call_count == best["tools"],
    )
    tokens_cell = _maybe_bold(
        _format_tokens_compact(r.total_tokens),
        eligible
        and best.get("tokens") is not None
        and r.total_tokens > 0
        and r.total_tokens == best["tokens"],
    )
    return (
        f"| {r.model} | {r.challenge_name} | {r.status} | "
        f"{time_cell} | {tools_cell} | {tokens_cell} | {verify_cell} |"
    )


def _write_detail_section(f, results: List[ChallengeResult]) -> None:
    f.write("\n\n## Detailed Results\n")
    for r in results:
        f.write(f"### {r.model} / {r.challenge_name}\n")
        f.write(f"- **Status:** {r.status}\n")
        f.write(f"- **Duration:** {r.duration:.2f}s\n")
        f.write(f"- **Workdir:** `{r.workdir}`\n")
        f.write(f"- **Log:** `{r.log_path}`\n")
        f.write(f"- **Tools Used:** {', '.join(r.tool_calls)}\n")
        f.write(
            f"- **Tokens:** total {r.total_tokens:,} "
            f"(input {r.input_tokens:,}, output {r.output_tokens:,}, "
            f"cache read {r.cache_read_tokens:,})\n"
        )
        if r.verification_output:
            f.write(
                f"\n**Verification Output:**\n```\n"
                f"{r.verification_output.strip()}\n```\n"
            )
        f.write("\n---\n")


def _compute_per_challenge_best(
    results: List[ChallengeResult],
) -> Dict[str, Dict[str, Optional[float]]]:
    """Per-challenge minimums of duration/tool_calls/total_tokens.

    Only EXCELLENT rows are eligible. Zero token counts (older runs
    missing the cost-summary line) and zero tool counts are excluded so
    they don't spuriously win.
    """
    buckets: Dict[str, Dict[str, List[float]]] = {}
    for r in results:
        if r.status != STATUS_EXCELLENT:
            continue
        b = buckets.setdefault(
            r.challenge_name, {"duration": [], "tools": [], "tokens": []}
        )
        b["duration"].append(r.duration)
        if r.tool_call_count > 0:
            b["tools"].append(r.tool_call_count)
        if r.total_tokens > 0:
            b["tokens"].append(r.total_tokens)
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for name, b in buckets.items():
        out[name] = {
            "duration": min(b["duration"]) if b["duration"] else None,
            "tools": min(b["tools"]) if b["tools"] else None,
            "tokens": min(b["tokens"]) if b["tokens"] else None,
        }
    return out


def _maybe_bold(text: str, condition: bool) -> str:
    return f"**{text}**" if condition else text


def _format_tokens_compact(total: int) -> str:
    """Render a token total as e.g. "478K" / "1.2M".

    Zero-token entries render as "—".
    """
    if total <= 0:
        return "—"
    if total < 1_000:
        return str(total)
    if total < 1_000_000:
        return f"{total / 1_000:.1f}K".replace(".0K", "K")
    return f"{total / 1_000_000:.2f}M".replace(".00M", "M")


def _summarize_verification(
    verification_output: Optional[str], status: str,
) -> str:
    """Pick a short table-cell note from the verifier's prefixed lines.

    Each verifier in ``challenges/*/verify.py`` emits prefixed lines:
        FAIL: <reason>    -- what failed
        WARN: <reason>    -- why this isn't EXCELLENT
        PASS: <reason>    -- what succeeded

    EXCELLENT → empty (the 🌟 icon speaks for itself).
    PASS      → first WARN if any, else last PASS.
    FAIL      → first non-tautological FAIL, optionally with (+N more).
    """
    if not verification_output or status == STATUS_EXCELLENT:
        return ""

    if status in (STATUS_FAIL, STATUS_VERIFY_FAILED):
        fails = _collect_verifier_lines(verification_output, "FAIL:")
        non_score = [
            f for f in fails if not f.lower().startswith("score too low")
        ]
        primary = non_score or fails
        if not primary:
            return _safe_verifier_cell("verifier rejected the output")
        extras = len(primary) - 1
        tail = f" (+{extras} more)" if extras else ""
        return _safe_verifier_cell(f"{primary[0]}{tail}")

    if status == STATUS_PASS:
        warns = _collect_verifier_lines(verification_output, "WARN:")
        if warns:
            return _safe_verifier_cell(warns[0])
        passes = _collect_verifier_lines(verification_output, "PASS:")
        return _safe_verifier_cell(passes[-1]) if passes else ""

    return ""


def _collect_verifier_lines(text: str, prefix: str) -> List[str]:
    """Verifier lines starting with ``prefix`` (e.g. ``FAIL:``), prefix stripped."""
    out: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            out.append(stripped[len(prefix):].strip())
    return out


def _safe_verifier_cell(text: str, limit: int = 90) -> str:
    """Flatten + escape verifier text so it fits a markdown table cell."""
    text = " ".join(text.split())
    text = re.sub(r"\s*\([^)]*/[^)]*\)", "", text)
    text = text.replace("|", "\\|")
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


def load_existing_results(json_path: Path) -> Dict[str, ChallengeResult]:
    """Load results from a previous run's ``results.json``, if any."""
    if not json_path.exists():
        return {}
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        out: Dict[str, ChallengeResult] = {}
        for item in data:
            r = ChallengeResult(**item)
            out[f"{r.model}/{r.challenge_name}"] = r
        return out
    except Exception as e:
        print(f"Warning: Failed to load existing results: {e}")
        return {}


def _save_results_json(json_path: Path, results: List[ChallengeResult]) -> None:
    with open(json_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def _discover_challenges(filter_spec: Optional[str]) -> List[Path]:
    challenges = [
        d for d in CHALLENGES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]
    if filter_spec:
        wanted = set(filter_spec.split(","))
        challenges = [c for c in challenges if c.name in wanted]
    return challenges


def _should_skip(
    prev: Optional[ChallengeResult], verbose: bool, key: str,
) -> bool:
    """Skip a cell only if a previous run reached a terminal outcome."""
    if prev is None or prev.status not in TERMINAL_STATUSES:
        return False
    if verbose:
        print(f"  Skipping {key} (already {prev.status})")
    return True


def main() -> None:
    config = parse_args()

    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    if not CHALLENGES_DIR.exists():
        print(f"Error: {CHALLENGES_DIR} not found.")
        return

    challenges = _discover_challenges(config.filter)
    if not challenges:
        print("No challenges found.")
        return

    print(f"Found {len(challenges)} challenges.")
    print(f"Models: {config.models}")
    print(f"Parallelism: {config.parallelism}")

    report_json = EXPERIMENT_BASE_DIR / "results.json"
    existing = load_existing_results(report_json)
    final_results: Dict[str, ChallengeResult] = existing.copy()

    print("\n=== Starting experiments ===")

    future_to_key: Dict[object, str] = {}
    with ThreadPoolExecutor(max_workers=config.parallelism) as executor:
        for model in config.models:
            for challenge in challenges:
                key = f"{model}/{challenge.name}"
                if _should_skip(existing.get(key), config.verbose, key):
                    continue
                if config.verbose:
                    print(f"  Scheduling: {model} / {challenge.name}")
                fut = executor.submit(
                    run_single_experiment,
                    challenge, model, config.timeout, config.verbose,
                )
                future_to_key[fut] = key

        for i, fut in enumerate(list(future_to_key)):
            if config.verbose:
                print(f"  Waiting for result {i + 1}/{len(future_to_key)}...")
            try:
                result = fut.result()
                final_results[future_to_key[fut]] = result
                if config.verbose:
                    print(f"  Got result: {result.status}")
            except Exception as e:
                print(f"  Error getting result: {e}")

    results = sorted(
        final_results.values(), key=lambda r: (r.model, r.challenge_name)
    )

    report_md = EXPERIMENT_BASE_DIR / "REPORT.md"
    generate_report(results, report_md)
    _save_results_json(report_json, results)

    print(f"\nExperiment Complete. Report saved to {report_md}")


if __name__ == "__main__":
    main()
