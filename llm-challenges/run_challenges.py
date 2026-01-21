import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configuration
CHALLENGES_DIR = Path("challenges")
EXPERIMENT_BASE_DIR = Path("experiment")
TIMEOUT_SECONDS = 300  # 5 minutes per challenge timeout


def run_command(command, cwd, stdout_file, stderr_file):
    """Runs a shell command, capturing output to files."""
    print(f"Executing: {' '.join(command)}")
    print(f"Working Directory: {cwd}")

    with open(stdout_file, "w") as out_f, open(stderr_file, "w") as err_f:
        try:
            # We use shell=False for safety, passing list of args
            process = subprocess.run(
                command,
                cwd=cwd,
                stdout=out_f,
                stderr=err_f,
                timeout=TIMEOUT_SECONDS,
                env={
                    **os.environ,
                    "ZRB_LLM_SHOW_TOOL_CALL_RESULT": "true",
                    "ZRB_LLM_SHOW_TOOL_CALL_DETAIL": "true",
                },
            )
            return process.returncode
        except subprocess.TimeoutExpired:
            err_f.write(f"\n\nTIMEOUT ({TIMEOUT_SECONDS}s) EXCEEDED\n")
            print(f"TIMEOUT exceeded for {cwd}")
            return 124  # Common timeout exit code


def setup_experiment(challenge_name, challenge_path):
    """Prepares the experiment directory."""
    experiment_dir = EXPERIMENT_BASE_DIR / challenge_name

    # 1. Clean up
    if experiment_dir.exists():
        shutil.rmtree(experiment_dir)

    # 2. Create dir
    experiment_dir.mkdir(parents=True, exist_ok=True)

    # 3. Copy workdir
    # Some challenges have a 'workdir' folder, some might be flat.
    # The TASK.md says: "cp -r challenges/refactor/* experiment/refactor/"
    # So we copy everything from the challenge source to the experiment dir.
    # However, we should be careful not to copy 'evaluation.md' or 'instruction.md'
    # if they are not meant to be seen by the agent, but typically the agent works in 'workdir'.

    # Let's follow TASK.md: "cp -r challenges/refactor/* experiment/refactor/"
    # And then "Execute from within the workdir directory of the experiment"

    shutil.copytree(challenge_path, experiment_dir, dirs_exist_ok=True)

    return experiment_dir


def run_challenge(challenge_dir):
    challenge_name = challenge_dir.name
    print(f"\n=== Running Challenge: {challenge_name} ===")

    # Setup
    experiment_dir = setup_experiment(challenge_name, challenge_dir)

    # Determine execution context
    # TASK.md: "Always execute from within the workdir directory of the experiment."
    workdir_dir = experiment_dir / "workdir"

    if not workdir_dir.exists():
        # Fallback if no workdir dir (e.g. copywriting might not have one)
        # But if TASK.md says "workdir", we should look for it.
        # If it doesn't exist, we run in the experiment root?
        # Let's check if 'workdir' exists in source.
        if (challenge_dir / "workdir").exists():
            # It should have been copied
            pass
        else:
            # If the challenge doesn't have workdir folder, we create one or run in root?
            # Let's assume we run in experiment_dir if workdir is missing,
            # but standard challenges seem to have it.
            print(
                f"Warning: 'workdir' directory not found for {challenge_name}. Running in root."
            )
            workdir_dir = experiment_dir

    # Instruction path (relative to the execution directory, or absolute)
    # The instruction is usually in the challenge root (parent of workdir)
    instruction_file = experiment_dir / "instruction.md"

    if not instruction_file.exists():
        print(f"Skipping {challenge_name}: instruction.md not found.")
        return

    instruction_text = instruction_file.read_text().strip()

    # Command
    # zrb --interactive false --yolo true --message "..."
    cmd = [
        "zrb",
        "chat",
        "--interactive",
        "false",
        "--yolo",
        "true",
        "--message",
        instruction_text,
    ]

    # Output files
    stdout_log = experiment_dir / "stdout.log"
    stderr_log = experiment_dir / "stderr.log"

    # Execute
    ret_code = run_command(cmd, workdir_dir, stdout_log, stderr_log)

    print(f"Finished {challenge_name}. Return Code: {ret_code}")
    print(f"Logs: {stdout_log}, {stderr_log}")


def main():
    # Ensure we are in the llm-challenges directory (or close to it)
    # The script is likely placed in llm-challenges/
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    print(f"Starting Challenge Suite in {script_dir}")

    # Find challenges
    if not CHALLENGES_DIR.exists():
        print(f"Error: {CHALLENGES_DIR} directory not found.")
        sys.exit(1)

    challenges = [
        d for d in CHALLENGES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]

    if not challenges:
        print("No challenges found.")
        sys.exit(0)

    print(f"Found {len(challenges)} challenges: {[c.name for c in challenges]}")

    for challenge in challenges:
        run_challenge(challenge)

    print("\n=== All Challenges Completed ===")


if __name__ == "__main__":
    main()
