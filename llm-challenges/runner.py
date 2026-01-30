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
DEFAULT_MODELS = ["default"]  # Can be overridden via CLI
DEFAULT_TIMEOUT = 1800  # 30 minutes

# Model configurations
MODEL_CONFIGS = {
    "gpt-4o": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "deepseek-chat": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "ZRB_LLM_API_KEY",
    },
    "default": {"base_url": None, "api_key_env": None},  # Use default
}


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


def parse_args() -> ExperimentConfig:
    parser = argparse.ArgumentParser(description="Run LLM Challenges")
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="List of models to test (e.g., gemini-1.5-pro gpt-4)",
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
    args = parser.parse_args()
    return ExperimentConfig(
        models=args.models,
        parallelism=args.parallelism,
        timeout=args.timeout,
        filter=args.filter,
    )


def extract_tool_calls(log_content: str) -> List[str]:
    # Regex to find tool usage in logs.
    # Zrb output format: "🧰 call_00_ID | tool_name {params}"
    matches = re.findall(r"🧰\s+\w+\s+\|\s+(\w+)", log_content)
    if not matches:
        # Fallback to other patterns
        matches = re.findall(r"Tool call: (\w+)", log_content)
    if not matches:
        # Fallback to checking for pydantic-ai style logs if visible
        matches = re.findall(r"tool='(\w+)'", log_content)
    return matches


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
    challenge_path: Path, model: str, timeout: int
) -> ChallengeResult:
    challenge_name = challenge_path.name
    exp_dir = EXPERIMENT_BASE_DIR / model / challenge_name

    # 1. Setup Directory
    if exp_dir.exists():
        shutil.rmtree(exp_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Copy challenge files
    shutil.copytree(challenge_path, exp_dir, dirs_exist_ok=True)

    workdir = exp_dir / "workdir"
    if not workdir.exists():
        workdir = exp_dir

    instruction_file = exp_dir / "instruction.md"
    if not instruction_file.exists():
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

    # Copy verification scripts to workdir for the agent to use
    src_verify_script = exp_dir / "verify.sh"
    src_verify_py = exp_dir / "verify.py"

    tgt_verify_script = workdir / "verify.sh"
    tgt_verify_py = workdir / "verify.py"

    if src_verify_script.exists() and not tgt_verify_script.exists():
        shutil.copy2(src_verify_script, tgt_verify_script)
    if src_verify_py.exists() and not tgt_verify_py.exists():
        shutil.copy2(src_verify_py, tgt_verify_py)

    # 2. Prepare Command with proper model configuration
    env = os.environ.copy()

    # Set model-specific configuration
    if model != "default":
        env["ZRB_LLM_MODEL"] = model

        # Set base URL and API key if configured
        if model in MODEL_CONFIGS:
            config = MODEL_CONFIGS[model]
            if config["base_url"]:
                env["ZRB_LLM_BASE_URL"] = config["base_url"]
            if config["api_key_env"] and config["api_key_env"] in os.environ:
                # Use the API key from the specified environment variable
                env["ZRB_LLM_API_KEY"] = os.environ[config["api_key_env"]]

    env["ZRB_LLM_SHOW_TOOL_CALL_RESULT"] = "true"
    env["ZRB_LLM_SHOW_TOOL_CALL_DETAIL"] = "true"

    # Hide the parent git repo from the agent to avoid confusion
    env["GIT_CEILING_DIRECTORIES"] = str(exp_dir.resolve())

    cmd = [
        "zrb",
        "chat",
        "--interactive",
        "false",
        "--yolo",
        "true",
        "--message",
        instruction,
    ]

    log_file = exp_dir / "combined.log"

    start_time = time.time()

    try:
        with open(log_file, "w") as f:
            process = subprocess.run(
                cmd,
                cwd=workdir,
                stdout=f,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout for easier parsing
                timeout=timeout,
                env=env,
            )
        exit_code = process.returncode
        status = "SUCCESS" if exit_code == 0 else "FAILURE"
    except subprocess.TimeoutExpired:
        exit_code = 124
        status = "TIMEOUT"
        with open(log_file, "a") as f:
            f.write(f"\n[Runner] Timeout of {timeout}s exceeded.\n")
    except Exception as e:
        exit_code = -1
        status = "ERROR"
        with open(log_file, "a") as f:
            f.write(f"\n[Runner] Exception: {e}\n")

    duration = time.time() - start_time

    # 3. Analyze Logs
    log_content = log_file.read_text() if log_file.exists() else ""
    tool_calls = extract_tool_calls(log_content)

    # 4. Verify
    v_code, v_out = run_verification(challenge_path, workdir)
    if v_code != 0 and status == "SUCCESS":
        status = "VERIFY_FAILED"

    return ChallengeResult(
        challenge_name=challenge_name,
        model=model,
        status=status,
        duration=duration,
        tool_calls=tool_calls,
        tool_call_count=len(tool_calls),
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
            verify_icon = "✅" if r.status == "SUCCESS" else "❌"
            if r.status == "VERIFY_FAILED":
                verify_icon = "⚠️"

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

    # Test with just one challenge first
    print("\n=== Starting experiments ===")

    tasks = []
    with ThreadPoolExecutor(max_workers=config.parallelism) as executor:
        for model in config.models:
            for challenge in challenges:
                print(f"  Scheduling: {model} / {challenge.name}")
                tasks.append(
                    executor.submit(
                        run_single_experiment, challenge, model, config.timeout
                    )
                )

    results = []
    for i, future in enumerate(tasks):
        print(f"  Waiting for result {i+1}/{len(tasks)}...")
        results.append(future.result())
        print(f"  Got result: {results[-1].status}")

    # Generate Reports
    report_md = EXPERIMENT_BASE_DIR / "REPORT.md"
    generate_report(results, report_md)

    # Save JSON data
    report_json = EXPERIMENT_BASE_DIR / "results.json"
    with open(report_json, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nExperiment Complete. Report saved to {report_md}")


if __name__ == "__main__":
    main()
