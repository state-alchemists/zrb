"""Checks for the voice-interaction prototype.

Run: python3 test_voice_interaction.py
Kept dependency-free (stdlib + the modules under test) so it runs anywhere.
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import hook_speak  # noqa: E402
import voice_speaker  # noqa: E402
from voice_speaker import clean_for_speech, truncate_for_speech  # noqa: E402

MARKDOWN_SAMPLE = """
## Result

I fixed the parser. Here is the diff:

```python
def parse(x):
    return x.strip()  # not a real fix
```

- The bug was in `parse()`
- See [the PR](https://github.com/x/y/pull/1) for details

| col | val |
|-----|-----|
| a   | 1   |

**Done** — no further action needed. \U0001f389
"""


class TestCleanup(unittest.TestCase):
    def test_strips_unlistenable_markup(self):
        cleaned = clean_for_speech(MARKDOWN_SAMPLE)
        # The whole point: nothing that reads as symbols should survive.
        for leak in ("```", "def parse", "https://", "|", "#", "*", "`"):
            self.assertNotIn(leak, cleaned, f"{leak!r} leaked into speech")
        self.assertNotIn("\U0001f389", cleaned, "emoji leaked into speech")

    def test_keeps_prose_and_link_labels(self):
        cleaned = clean_for_speech(MARKDOWN_SAMPLE)
        self.assertIn("I fixed the parser", cleaned)
        self.assertIn("the PR", cleaned, "link label should survive")
        self.assertIn("no further action needed", cleaned)

    def test_empty_input(self):
        self.assertEqual(clean_for_speech(""), "")
        self.assertEqual(clean_for_speech("```only code```"), "")

    def test_truncation_prefers_sentence_boundary(self):
        text = "First sentence here. Second sentence here. Third sentence here."
        result = truncate_for_speech(text, 45)
        self.assertTrue(result.endswith("."), f"should cut at a sentence: {result!r}")
        self.assertNotIn("Third", result)

    def test_truncation_hard_cuts_without_sentence_break(self):
        result = truncate_for_speech("a" * 100, 20)
        self.assertTrue(result.endswith("..."))

    def test_truncation_noop_when_short(self):
        self.assertEqual(truncate_for_speech("short", 100), "short")


class TestSpeakSerialization(unittest.TestCase):
    def setUp(self):
        self.tmp = Path("/tmp") / f"zrb-voice-test-{os.getpid()}.lock"
        voice_speaker.LOCK_PATH = self.tmp

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)

    def test_dispatch_reaches_backend(self):
        with mock.patch.dict(os.environ, {"ZRB_VOICE_BACKEND": "espeak-ng"}):
            with mock.patch.object(voice_speaker, "_speak_espeak") as backend:
                voice_speaker.speak("hello there")
        backend.assert_called_once()
        spoken = backend.call_args[0][0]
        self.assertIn("hello there", spoken)

    def test_empty_text_never_reaches_backend(self):
        with mock.patch.object(voice_speaker, "_speak_espeak") as backend:
            voice_speaker.speak("")
            voice_speaker.speak("```code only```")
        backend.assert_not_called()

    def test_backend_exception_is_swallowed(self):
        """A broken backend must not raise -- the hook has to exit 0."""
        with mock.patch.object(
            voice_speaker, "_speak_espeak", side_effect=RuntimeError("device busy")
        ):
            voice_speaker.speak("this should not raise")

    def test_lock_is_released_after_speaking(self):
        with mock.patch.object(voice_speaker, "_speak_espeak"):
            voice_speaker.speak("first")
            voice_speaker.speak("second")  # would deadlock if the lock leaked


class TestHookContract(unittest.TestCase):
    """The hook must never signal anything back to zrb."""

    def _run(self, event, payload):
        data = json.dumps(payload)
        with mock.patch.dict(
            os.environ, {"CLAUDE_HOOK_EVENT": event}, clear=False
        ), mock.patch.object(sys, "stdin", io.StringIO(data)), mock.patch.object(
            hook_speak, "speak"
        ) as speak_mock:
            code = hook_speak.main()
        return code, speak_mock

    def test_stop_speaks_the_response(self):
        code, speak_mock = self._run("Stop", {"output": "All tests pass."})
        self.assertEqual(code, 0, "hook must exit 0 or zrb re-runs the turn")
        self.assertIn("All tests pass", speak_mock.call_args[0][0])

    def test_stop_skips_nested_subagent_runs(self):
        code, speak_mock = self._run(
            "Stop", {"output": "sub-agent chatter", "nested_run": True}
        )
        self.assertEqual(code, 0)
        speak_mock.assert_not_called()

    def test_permission_request_speaks_approval(self):
        code, speak_mock = self._run(
            "PermissionRequest",
            {"tool_name": "Write", "args": {"path": "/tmp/x.py"}},
        )
        self.assertEqual(code, 0)
        said = speak_mock.call_args[0][0]
        self.assertIn("approval", said.lower())
        self.assertIn("/tmp/x.py", said)

    def test_permission_request_unknown_tool_still_speaks(self):
        code, speak_mock = self._run(
            "PermissionRequest", {"tool_name": "SomeNewTool", "args": {}}
        )
        self.assertEqual(code, 0)
        self.assertIn("SomeNewTool", speak_mock.call_args[0][0])

    def test_notification_speaks_question(self):
        code, speak_mock = self._run(
            "Notification",
            {
                "notification_type": "elicitation_dialog",
                "message": "Waiting for your answer to a question",
            },
        )
        self.assertEqual(code, 0)
        speak_mock.assert_called_once()

    def test_notification_ignores_unactionable_types(self):
        code, speak_mock = self._run(
            "Notification", {"notification_type": "something_else", "message": "noise"}
        )
        self.assertEqual(code, 0)
        speak_mock.assert_not_called()

    def test_malformed_stdin_exits_clean(self):
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": "Stop"}, clear=False), \
                mock.patch.object(sys, "stdin", io.StringIO("{not json")):
            self.assertEqual(hook_speak.main(), 0)

    def test_empty_stdin_exits_clean(self):
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": "Stop"}, clear=False), \
                mock.patch.object(sys, "stdin", io.StringIO("")):
            self.assertEqual(hook_speak.main(), 0)

    def test_unknown_event_is_ignored(self):
        code, speak_mock = self._run("SessionStart", {"source": "startup"})
        self.assertEqual(code, 0)
        speak_mock.assert_not_called()

    def test_handler_exception_still_exits_zero(self):
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": "Stop"}, clear=False), \
                mock.patch.object(sys, "stdin", io.StringIO('{"output": "hi"}')), \
                mock.patch.object(
                    hook_speak, "handle_stop", side_effect=RuntimeError("boom")
                ):
            self.assertEqual(hook_speak.main(), 0)


class TestPayloadChannels(unittest.TestCase):
    """Regression: zrb puts the event payload in CLAUDE_EVENT_DATA, NOT stdin.

    Verified against zrb 3.0.0 -- stdin carries only the Claude envelope
    (session_id, cwd, hook_event_name, ...). Reading stdin alone silently
    produced no speech, which is exactly what this guards.
    """

    ENVELOPE = (
        '{"session_id": null, "cwd": "/tmp", '
        '"hook_event_name": "Stop", "permission_mode": "default"}'
    )

    def test_output_read_from_event_data_not_stdin(self):
        with mock.patch.object(sys, "stdin", io.StringIO(self.ENVELOPE)), \
                mock.patch.dict(
                    os.environ, {"CLAUDE_EVENT_DATA": '{"output": "real text"}'}
                ):
            payload = hook_speak._read_payload()
        self.assertEqual(payload["output"], "real text", "must read CLAUDE_EVENT_DATA")
        self.assertEqual(payload["hook_event_name"], "Stop", "envelope still merged")

    def test_stdin_alone_yields_no_output(self):
        """Documents the original bug: the envelope has no `output` key."""
        with mock.patch.object(sys, "stdin", io.StringIO(self.ENVELOPE)), \
                mock.patch.dict(os.environ, {}, clear=True):
            payload = hook_speak._read_payload()
        self.assertNotIn("output", payload)

    def test_event_data_wins_on_conflict(self):
        with mock.patch.object(sys, "stdin", io.StringIO('{"output": "wrong"}')), \
                mock.patch.dict(os.environ, {"CLAUDE_EVENT_DATA": '{"output": "right"}'}):
            self.assertEqual(hook_speak._read_payload()["output"], "right")

    def test_malformed_event_data_falls_back_to_stdin(self):
        with mock.patch.object(sys, "stdin", io.StringIO(self.ENVELOPE)), \
                mock.patch.dict(os.environ, {"CLAUDE_EVENT_DATA": "{not json"}):
            payload = hook_speak._read_payload()
        self.assertEqual(payload["hook_event_name"], "Stop")

    def test_stop_end_to_end_through_event_data(self):
        """The exact production path: event data on env, envelope on stdin."""
        with mock.patch.object(sys, "stdin", io.StringIO(self.ENVELOPE)), \
                mock.patch.dict(
                    os.environ,
                    {
                        "CLAUDE_HOOK_EVENT": "Stop",
                        "CLAUDE_EVENT_DATA": '{"output": "## Hi\\n\\nAll done."}',
                    },
                ), mock.patch.object(hook_speak, "speak") as speak_mock:
            code = hook_speak.main()
        self.assertEqual(code, 0)
        speak_mock.assert_called_once()
        self.assertIn("All done", speak_mock.call_args[0][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
