#!/usr/bin/env python3
"""zrb hook: speak agent output, approval prompts, and questions aloud.

Wired to three events (see hooks.json.example):

  Stop               -> speak a summary of the turn's response
  PermissionRequest  -> announce that a tool needs approval
  Notification       -> announce that a question is waiting

Contract this script must honour, and why:

* ALWAYS exit 0. Stop and PermissionRequest are both in zrb's BLOCKING_EVENTS
  (zrb/llm/hook/types.py). Exit 2 on Stop makes zrb re-run the whole turn with
  the stderr text injected as a new prompt -- the response gets regenerated and
  spoken again, bounded only by STOP_HOOK_BLOCK_CAP = 8. Exit 2 on
  PermissionRequest would block the user's approval prompt outright.
* Never write to stdout. On Stop, stdout is parsed as the JSON control
  protocol; on SessionStart/UserPromptSubmit plain stdout is injected into the
  model's context. Printing there changes agent behaviour.
* Never write to stderr either. On exit 2, stderr IS the block reason.
  Diagnostics go to the side log (voice_speaker.SPEAK_LOG).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice_speaker import log, speak  # noqa: E402


def _read_stdin() -> dict:
    """The Claude-standard envelope, delivered as JSON on stdin.

    VERIFIED against zrb 3.0.0: for a Stop event this contains ONLY session_id,
    transcript_path, cwd, permission_mode and hook_event_name. It does NOT
    contain `output`. Reading stdin alone yields silence -- see _read_event_data.
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log(f"stdin parse failed: {exc}")
        return {}


def _read_event_data() -> dict:
    """The actual event payload, delivered as a JSON string in CLAUDE_EVENT_DATA.

    This is where `output`, `tool_name`, `args`, `notification_type` and the
    rest live. A value over 16 KiB is dropped by zrb (creator.py
    _MAX_HOOK_ENV_BYTES) -- a very long response arrives truncated here and
    simply results in a shorter utterance, never an error.
    """
    raw = os.getenv("CLAUDE_EVENT_DATA")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log(f"event-data parse failed: {exc}")
        return {}


def _read_payload() -> dict:
    """Merge both channels into one payload.

    `CLAUDE_EVENT_DATA` wins on conflict because it holds the event-specific
    data; stdin only ever supplies the envelope.
    """
    return {**_read_stdin(), **_read_event_data()}


def _summarize(text: str) -> str:
    """What to say for a Stop event.

    Deterministic by default (see README for why an LLM summary is opt-in).
    Set ZRB_VOICE_SUMMARY=llm to route through a model instead.
    """
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
    """A human sentence for an approval prompt.

    PermissionRequest carries `tool_name` and a raw `args` dict. There is no
    rendered description, and the user is *waiting* on this -- so a template is
    used rather than an LLM call. `message` from zrb (e.g. "Approval requested
    to run Write") is a reasonable fallback.
    """
    tool = payload.get("tool_name") or (payload.get("tool") or {}).get("name")
    args = payload.get("args") or (payload.get("tool") or {}).get("args") or {}

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
    output = payload.get("output")
    if not output or not isinstance(output, str):
        # Loud in the log on purpose: a silent no-op here is indistinguishable
        # from "the hook never fired", which is very hard to debug.
        log(f"stop: NO OUTPUT (keys={sorted(payload)}); check CLAUDE_EVENT_DATA")
        return
    # A sub-agent's Stop fires on the parent's manager too; speaking both the
    # sub-agent's chatter and the final answer is noise.
    if payload.get("nested_run"):
        log("stop: nested run, skipping")
        return
    speak(_summarize(output))


def handle_permission_request(payload: dict) -> None:
    speak(_describe_tool_call(payload))


def handle_notification(payload: dict) -> None:
    notification_type = payload.get("notification_type")
    # zrb fires Notification for more than questions; only announce the one the
    # user actually has to act on, or this becomes a chatty interrupter.
    if notification_type not in ("elicitation_dialog", "permission_prompt"):
        log(f"notification: ignored type={notification_type!r}")
        return
    message = payload.get("message") or "A question is waiting for your answer."
    speak(message)


HANDLERS = {
    "Stop": handle_stop,
    "PermissionRequest": handle_permission_request,
    "Notification": handle_notification,
}


def main() -> int:
    event = os.getenv("CLAUDE_HOOK_EVENT") or ""
    payload = _read_payload()
    if not event:
        event = payload.get("hook_event_name") or ""

    handler = HANDLERS.get(event)
    if handler is None:
        log(f"ignored event {event!r}")
        return 0

    try:
        handler(payload)
    except Exception as exc:
        log(f"handler {event} raised: {type(exc).__name__}: {exc}")
    # Unconditional: see module docstring.
    return 0


if __name__ == "__main__":
    sys.exit(main())
