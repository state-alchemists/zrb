#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
CHALLENGES_DIR = Path("challenges")
EXPERIMENT_BASE_DIR = Path("experiment")
DEFAULT_MODELS = [""]  # Can be overridden via CLI
DEFAULT_TIMEOUT = 3600  # 30 minutes


@dataclass
class ChallengeResult:
    challenge_name: str
    model: str
    status: str  # "SUCCESS", "FAILURE", "TIMEOUT", "ERROR"
    duration: float
    tool_calls: List[str]
    tool_call_count: int
    exit_code: int
    log_path: str
    workdir: str
    verification_output: Optional[str] = None


@dataclass
class ExperimentConfig:
    models: List[str]
    parallelism: int
    timeout: int
    filter: Optional[str] = None
    verbose: bool = False  # New: Verbose output mode


def parse_args() -> ExperimentConfig:
    parser = argparse.ArgumentParser(
        description="Run LLM Challenges - Enhanced with test_single.py features"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="List of models to test (e.g., google-gla:gemini-2.5-flash google-gla:gemini-1.5-pro openai:gpt-4o deepseek:deepseek-chat)",
    )
    parser.add_argument(
        "--parallelism", type=int, default=4, help="Number of concurrent experiments"
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Filter challenges by name (comma-separated)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Timeout per challenge in seconds",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show verbose output"
    )
    args = parser.parse_args()

    return ExperimentConfig(
        models=args.models,
        parallelism=args.parallelism,
        timeout=args.timeout,
        filter=args.filter,
        verbose=args.verbose,
    )


def extract_tool_calls(log_content: str) -> List[str]:
    """Enhanced tool call extraction from test_single.py"""
    # Primary detection: Zrb tool call emoji "🧰"
    matches = re.findall(r"🧰\s+\w+\s+\|\s+(\w+)", log_content)
    if not matches:
        # Secondary detection: Just count "🧰" occurrences
        if "🧰" in log_content:
            # Extract tool names from surrounding context
            pattern = r"🧰[^|]+\|\s*(\w+)"
            matches = re.findall(pattern, log_content)
    if not matches:
        # Fallback to other patterns
        matches = re.findall(r"Tool call: (\w+)", log_content)
    if not matches:
        # Fallback to checking for pydantic-ai style logs if visible
        matches = re.findall(r"tool='(\w+)'", log_content)
    return matches


def count_tool_calls(log_content: str) -> int:
    """Count tool calls by looking for the tool emoji"""
    return log_content.count("🧰")


def run_verification(challenge_dir: Path, workdir: Path) -> tuple[int, str]:
    """Runs verify.sh or verify.py if present in the challenge dir."""
    # Copy verify scripts to workdir to ensure they run in the correct context
    src_verify_script = challenge_dir / "verify.sh"
    src_verify_py = challenge_dir / "verify.py"

    verify_script = workdir / "verify.sh"
    verify_py = workdir / "verify.py"

    if src_verify_script.exists():
        shutil.copy2(src_verify_script, verify_script)
    if src_verify_py.exists():
        shutil.copy2(src_verify_py, verify_py)

    output = ""
    code = 0

    if verify_script.exists():
        try:
            # Make executable
            verify_script.chmod(verify_script.stat().st_mode | 0o111)
            res = subprocess.run(
                ["bash", "./verify.sh"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            code = res.returncode
            output = res.stdout + "\n" + res.stderr
        except Exception as e:
            code = -1
            output = str(e)
    elif verify_py.exists():
        try:
            res = subprocess.run(
                ["python3", "verify.py"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            code = res.returncode
            output = res.stdout + "\n" + res.stderr
        except Exception as e:
            code = -1
            output = str(e)

    return code, output


def run_single_experiment(
    challenge_path: Path, model: str, timeout: int, verbose: bool = False
) -> ChallengeResult:
    """Enhanced single experiment runner with test_single.py features"""
    challenge_name = challenge_path.name
    exp_dir = EXPERIMENT_BASE_DIR / model / challenge_name

    if verbose:
        print(f"\n{'='*60}")
        print(f"Testing {model} on {challenge_name} challenge")
        print(f"{'='*60}")

    # 1. Setup Directory
    if exp_dir.exists():
        shutil.rmtree(exp_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Prepare Workdir
    # ONLY copy the 'workdir' folder to the experiment to prevent cheating
    # (Agent cannot see verify.py, instruction.md, etc.)
    source_workdir = challenge_path / "workdir"
    workdir = exp_dir / "workdir"

    shutil.copytree(source_workdir, workdir, dirs_exist_ok=True)

    # Read Instruction from SOURCE
    instruction_file = challenge_path / "instruction.md"
    if not instruction_file.exists():
        if verbose:
            print(f"ERROR: {instruction_file} not found")
        return ChallengeResult(
            challenge_name=challenge_name,
            model=model,
            status="ERROR",
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

    # 2. Prepare Command with enhanced model configuration from test_single.py
    env = os.environ.copy()
    env["ZRB_LLM_SHOW_TOOL_CALL_RESULT"] = "true"
    env["ZRB_LLM_SHOW_TOOL_CALL_DETAIL"] = "true"
    # Hide the parent git repo from the agent to avoid confusion
    env["GIT_CEILING_DIRECTORIES"] = str(exp_dir.resolve())

    cmd = [
        "zrb",
        "chat",
        "--model",
        model,
        "--interactive",
        "false",
        "--yolo",
        "true",
        "--message",
        instruction,
    ]

    if verbose:
        print(f"Command: {' '.join(cmd[:4])} [message hidden]")
        print(f"Timeout: {timeout}s")

    log_file = exp_dir / "combined.log"

    start_time = time.time()
    exit_code = 0
    status = "SUCCESS"

    try:
        if verbose:
            print(f"{model} Running command...")
            # For verbose mode, we can capture and show output in real-time
            with open(log_file, "w") as f:
                process = subprocess.Popen(
                    cmd,
                    cwd=workdir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                # Read output in real-time
                for line in process.stdout:
                    f.write(line)
                    if verbose and "🧰" in line:
                        print(f"  {model} Tool call detected: {line.strip()[:100]}...")

                process.wait(timeout=timeout)
                exit_code = process.returncode
        else:
            # Non-verbose mode: use original approach
            with open(log_file, "w") as f:
                process = subprocess.run(
                    cmd,
                    cwd=workdir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    env=env,
                )
                exit_code = process.returncode

        status = "EXECUTION_COMPLETE" if exit_code == 0 else "EXECUTION_FAILED"

    except subprocess.TimeoutExpired:
        exit_code = 124
        status = "TIMEOUT"
        with open(log_file, "a") as f:
            f.write(f"\n[Runner] Timeout of {timeout}s exceeded.\n")
        if verbose:
            print(f"❌ {model} Timeout after {timeout}s")
    except Exception as e:
        exit_code = -1
        status = "ERROR"
        with open(log_file, "a") as f:
            f.write(f"\n[Runner] Exception: {e}\n")
        if verbose:
            print(f"❌ {model} Error: {e}")

    duration = time.time() - start_time

    # 3. Analyze Logs with enhanced tool call detection
    log_content = log_file.read_text() if log_file.exists() else ""
    tool_calls = extract_tool_calls(log_content)
    tool_call_count = count_tool_calls(log_content)

    if verbose:
        print(f"\n{model} Result after {duration:.1f}s:")
        print(f"{model} Exit code: {exit_code}")

        # Enhanced tool call reporting from test_single.py
        if tool_call_count > 0:
            print(f"✅ Tool calls detected: {tool_call_count}")
            if tool_calls:
                print(
                    f"{model} Tools used: {', '.join(tool_calls[:5])}"
                    + ("..." if len(tool_calls) > 5 else "")
                )
        else:
            print("⚠️ No tool calls detected")

    # 4. Verify
    v_code, v_out = run_verification(challenge_path, workdir)

    # Determine final status based on verification output
    if status == "EXECUTION_COMPLETE":
        if "VERIFICATION_RESULT: EXCELLENT" in v_out:
            status = "EXCELLENT"
        elif "VERIFICATION_RESULT: PASS" in v_out:
            status = "PASS"
        elif "VERIFICATION_RESULT: FAIL" in v_out:
            status = "FAIL"
        elif v_code == 0:
            # Fallback for legacy verify scripts
            status = "PASS"
        else:
            status = "FAIL"

    if verbose:
        print(f"Final Status: {status}")
        if v_code != 0:
            print(f"⚠️ {model} Verification script exit code: {v_code}")

    return ChallengeResult(
        challenge_name=challenge_name,
        model=model,
        status=status,
        duration=duration,
        tool_calls=tool_calls,
        tool_call_count=tool_call_count,
        exit_code=exit_code,
        log_path=str(log_file),
        workdir=str(workdir),
        verification_output=v_out if v_out else None,
    )


def generate_report(results: List[ChallengeResult], output_file: Path):
    with open(output_file, "w") as f:
        f.write("# LLM Challenge Experiment Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Summary Table
        f.write("| Model | Challenge | Status | Time (s) | Tools | Verify |\n")
        f.write("|---|---|---|---|---|---|\n")

        for r in results:
            verify_icon = "❓"
            if r.status == "EXCELLENT":
                verify_icon = "🌟"
            elif r.status == "PASS":
                verify_icon = "✅"
            elif r.status == "FAIL" or r.status == "VERIFY_FAILED":
                verify_icon = "❌"
            elif r.status == "TIMEOUT":
                verify_icon = "⏱️"
            elif r.status == "EXECUTION_FAILED" or r.status == "ERROR":
                verify_icon = "💥"

            f.write(
                f"| {r.model} | {r.challenge_name} | {r.status} | {r.duration:.2f} | {r.tool_call_count} | {verify_icon} |\n"
            )

        f.write("\n\n## Detailed Results\n")
        for r in results:
            f.write(f"### {r.model} / {r.challenge_name}\n")
            f.write(f"- **Status:** {r.status}\n")
            f.write(f"- **Duration:** {r.duration:.2f}s\n")
            f.write(f"- **Workdir:** `{r.workdir}`\n")
            f.write(f"- **Log:** `{r.log_path}`\n")
            f.write(f"- **Tools Used:** {', '.join(r.tool_calls)}\n")
            if r.verification_output:
                f.write(
                    f"\n**Verification Output:**\n```\n{r.verification_output.strip()}\n```\n"
                )
            f.write("\n---\n")


def load_existing_results(json_path: Path) -> Dict[str, ChallengeResult]:
    """Load existing results from JSON file."""
    if not json_path.exists():
        return {}
    
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
            results = {}
            for item in data:
                # Convert dictionary back to ChallengeResult
                result = ChallengeResult(**item)
                key = f"{result.model}/{result.challenge_name}"
                results[key] = result
            return results
    except Exception as e:
        print(f"Warning: Failed to load existing results: {e}")
        return {}


def main():
    config = parse_args()

    # Locate challenges
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    if not CHALLENGES_DIR.exists():
        print(f"Error: {CHALLENGES_DIR} not found.")
        return

    challenges = [
        d for d in CHALLENGES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]

    if config.filter:
        filter_names = config.filter.split(",")
        challenges = [c for c in challenges if c.name in filter_names]

    if not challenges:
        print("No challenges found.")
        return

    print(f"Found {len(challenges)} challenges.")
    print(f"Models: {config.models}")
    print(f"Parallelism: {config.parallelism}")

    # Load existing results
    report_json = EXPERIMENT_BASE_DIR / "results.json"
    existing_results = load_existing_results(report_json)
    
    # Track final results (start with existing ones)
    final_results_map = existing_results.copy()

    print("\n=== Starting experiments ===")

    tasks = []
    # We need to keep track of which futures correspond to which key to update the map later
    future_to_key = {}

    with ThreadPoolExecutor(max_workers=config.parallelism) as executor:
        for model in config.models:
            for challenge in challenges:
                key = f"{model}/{challenge.name}"
                
                # Check if we should skip
                skip = False
                if key in existing_results:
                    prev_result = existing_results[key]
                    # Retry only if failed, execution failed, error or timeout
                    # i.e., Skip if status is PASS, EXCELLENT, SUCCESS
                    if prev_result.status in ["PASS", "EXCELLENT", "SUCCESS"]:
                        skip = True
                        if config.verbose:
                            print(f"  Skipping {key} (already {prev_result.status})")
                
                if not skip:
                    if config.verbose:
                        print(f"  Scheduling: {model} / {challenge.name}")
                    
                    future = executor.submit(
                        run_single_experiment,
                        challenge,
                        model,
                        config.timeout,
                        config.verbose,
                    )
                    tasks.append(future)
                    future_to_key[future] = key
                else:
                    # Ensure the skipped result is in the final map (it's already there from copy)
                    pass

    # Collect new results
    for i, future in enumerate(tasks):
        if config.verbose:
            print(f"  Waiting for result {i+1}/{len(tasks)}...")
        
        try:
            result = future.result()
            key = future_to_key[future]
            final_results_map[key] = result
            
            if config.verbose:
                print(f"  Got result: {result.status}")
        except Exception as e:
            print(f"  Error getting result: {e}")

    # Prepare final list for reporting
    results = list(final_results_map.values())
    
    # Sort results for consistent output (by model then challenge)
    results.sort(key=lambda x: (x.model, x.challenge_name))

    # Generate Reports
    report_md = EXPERIMENT_BASE_DIR / "REPORT.md"
    generate_report(results, report_md)

    # Save JSON data
    with open(report_json, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nExperiment Complete. Report saved to {report_md}")


if __name__ == "__main__":
    main()
