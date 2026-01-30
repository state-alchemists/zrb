#!/usr/bin/env python3
"""
Simple test to verify gpt-4o and deepseek-chat work with ONE challenge.
Run this first to verify your setup works.
"""
import os
import subprocess
import time
from pathlib import Path


def test_model(model: str, challenge: str = "bug-fix", timeout: int = 120):
    """Test a single model with a single challenge."""
    print(f"\n{'='*60}")
    print(f"Testing {model} on {challenge} challenge")
    print(f"{'='*60}")

    # Prepare environment
    env = os.environ.copy()
    env["ZRB_LLM_MODEL"] = model

    # Model-specific configuration
    if model == "gpt-4o":
        env["ZRB_LLM_BASE_URL"] = "https://api.openai.com/v1"
        if "OPENAI_API_KEY" in os.environ:
            env["ZRB_LLM_API_KEY"] = os.environ["OPENAI_API_KEY"]
    elif model == "deepseek-chat":
        env["ZRB_LLM_BASE_URL"] = "https://api.deepseek.com/v1"
        if "ZRB_LLM_API_KEY" in os.environ:
            env["ZRB_LLM_API_KEY"] = os.environ["ZRB_LLM_API_KEY"]

    env["ZRB_LLM_SHOW_TOOL_CALL_RESULT"] = "true"

    # Read the challenge instruction
    instruction_file = Path("challenges") / challenge / "instruction.md"
    if not instruction_file.exists():
        print(f"ERROR: {instruction_file} not found")
        return False

    instruction = instruction_file.read_text().strip()
    print(f"Instruction: {instruction[:100]}...")

    # Run zrb chat
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

    print(f"Command: {' '.join(cmd[:4])} [message hidden]")
    print(f"Timeout: {timeout}s")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
        )

        duration = time.time() - start_time
        print(f"\nResult after {duration:.1f}s:")
        print(f"Exit code: {result.returncode}")

        # Check for tool calls
        if "🧰" in result.stdout:
            print("✅ Tool calls detected")
            # Count tool calls
            tool_count = result.stdout.count("🧰")
            print(f"Tool calls made: {tool_count}")
        else:
            print("⚠️ No tool calls detected")

        # Check for errors
        if result.returncode != 0:
            print(f"❌ Failed with exit code {result.returncode}")
            if result.stderr:
                print(f"Stderr: {result.stderr[:200]}...")
            return False
        else:
            print("✅ Success!")
            return True

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"\n❌ Timeout after {duration:.1f}s")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run simple tests."""
    print("Testing LLM Framework with gpt-4o and deepseek-chat")
    print("This will test ONE challenge (bug-fix) to verify setup works.")

    # Test both models
    models = ["gpt-4o", "deepseek-chat"]
    results = {}

    for model in models:
        success = test_model(model, challenge="bug-fix", timeout=60)
        results[model] = success

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for model, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{model}: {status}")

    if all(results.values()):
        print("\n✅ Both models work! You can now run the full test:")
        print("  python3 runner.py --models gpt-4o deepseek-chat --parallelism 2")
    else:
        print("\n⚠️ Some tests failed. Check your API keys and configuration.")


if __name__ == "__main__":
    main()
