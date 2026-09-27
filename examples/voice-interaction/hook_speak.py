#!/usr/bin/env python3
"""zrb hook: speak agent output, approval prompts, and questions aloud.

Wired to Stop, PermissionRequest and Notification in .zrb/hooks.json.

Always exits 0 and never writes to stdout or stderr: on Stop, exit 2 re-runs
the turn with stderr as the new prompt, and stdout is parsed as JSON control
output. Diagnostics go to the side log (voice_speaker.SPEAK_LOG).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice_speaker import log, speak  # noqa: E402


def _read_payload() -> dict:
    """The Claude-shaped JSON zrb writes to stdin."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log(f"stdin parse failed: {exc}")
        return {}


def _summarize(text: str) -> str:
    if os.getenv("ZRB_VOICE_SUMMARY", "clean").strip().lower() == "llm":
        try:
            from llm_summary import summarize_with_llm

            summarized = summarize_with_llm(text)
            if summarized:
                return summarized
        except Exception as exc:
            log(f"llm summary failed, falling back to cleanup: {exc}")
    return text


def _describe_tool_call(payload: dict) -> str:
    """A template, not an LLM call: the user is waiting on this prompt."""
    tool = payload.get("tool_name")
    args = payload.get("tool_input") or {}
    friendly = {
        "Write": "write a file",
        "Edit": "edit a file",
        "NotebookEdit": "edit a notebook",
        "Shell": "run a shell command",
        "Bash": "run a shell command",
        "DelegateToAgent": "delegate work to a sub-agent",
        "DelegateToAgentBackground": "delegate background work to a sub-agent",
    }.get(tool, f"use the {tool} tool" if tool else "run a tool")

    target = ""
    if isinstance(args, dict):
        for key in ("path", "file_path", "command", "notebook_path"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                target = " " + value.strip()[:80]
                break
    return f"I need to {friendly}{target}. I need your approval."


def handle_stop(payload: dict) -> None:
    output = payload.get("last_assistant_message")
    if not output or not isinstance(output, str):
        log(f"stop: no last_assistant_message (keys={sorted(payload)})")
        return
    speak(_summarize(output))


def handle_permission_request(payload: dict) -> None:
    speak(_describe_tool_call(payload))


def handle_notification(payload: dict) -> None:
    # Only the notifications the user has to act on.
    if payload.get("notification_type") not in (
        "elicitation_dialog",
        "permission_prompt",
    ):
        log(f"notification: ignored type={payload.get('notification_type')!r}")
        return
    speak(payload.get("message") or "A question is waiting for your answer.")


HANDLERS = {
    "Stop": handle_stop,
    "PermissionRequest": handle_permission_request,
    "Notification": handle_notification,
}


def main() -> int:
    payload = _read_payload()
    event = os.getenv("CLAUDE_HOOK_EVENT") or payload.get("hook_event_name") or ""
    handler = HANDLERS.get(event)
    if handler is None:
        log(f"ignored event {event!r}")
        return 0
    try:
        handler(payload)
    except Exception as exc:
        log(f"handler {event} raised: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
