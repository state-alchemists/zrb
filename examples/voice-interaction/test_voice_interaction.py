"""Checks for the voice-interaction prototype.

Run: python3 test_voice_interaction.py
Kept dependency-free (stdlib + the modules under test) so it runs anywhere.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import hook_speak  # noqa: E402
import voice_speaker  # noqa: E402
from voice_speaker import clean_for_speech, truncate_for_speech  # noqa: E402

voice_speaker.SPEAK_LOG = Path(tempfile.gettempdir()) / "zrb-voice-test.log"

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

    def test_strips_tables_without_outer_pipes(self):
        cleaned = clean_for_speech("Results:\n\ncol | val\n--- | :-:\na | 1\n\nAll done.")
        self.assertNotIn("|", cleaned)
        self.assertNotIn("---", cleaned)
        self.assertIn("All done", cleaned)

    def test_keeps_a_pipe_in_prose_and_drops_rules(self):
        cleaned = clean_for_speech("Intro.\n\n---\n\nUse a | b here.")
        self.assertIn("a | b", cleaned)
        self.assertNotIn("---", cleaned)

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

    def test_dispatch_reaches_player(self):
        with mock.patch.dict(os.environ, {"ZRB_VOICE_BACKEND": "auto"}), \
                mock.patch.object(voice_speaker, "run_player") as player:
            voice_speaker.speak("hello there")
        player.assert_called_once()
        argv = player.call_args[0][0]
        self.assertIn("hello there", argv[-1])

    def test_empty_text_never_reaches_player(self):
        with mock.patch.object(voice_speaker, "run_player") as player:
            voice_speaker.speak("")
            voice_speaker.speak("```code only```")
        player.assert_not_called()

    def test_player_failure_is_swallowed(self):
        """A broken player must not raise -- the hook has to exit 0."""
        with mock.patch.object(
            voice_speaker.subprocess, "run", side_effect=RuntimeError("device busy")
        ):
            voice_speaker.run_player(["say", "x"], "this should not raise")

    def test_is_speaking_tracks_the_player(self):
        """The hands-free listener mutes the mic on this; it must see playback."""
        seen = []
        with mock.patch.object(
            voice_speaker.subprocess, "run",
            side_effect=lambda *a, **k: seen.append(voice_speaker.is_speaking()),
        ):
            self.assertFalse(voice_speaker.is_speaking())
            voice_speaker.run_player(["say", "x"])
        self.assertEqual(seen, [True], "lock must be visible during playback")
        self.assertFalse(voice_speaker.is_speaking(), "and released after")

    def test_lock_is_released_after_playing(self):
        with mock.patch.object(voice_speaker.subprocess, "run"):
            voice_speaker.run_player(["say", "first"])
            voice_speaker.run_player(["say", "second"])  # deadlocks if leaked


class TestLog(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.gettempdir()) / f"zrb-voice-log-test-{os.getpid()}.log"
        self.path.unlink(missing_ok=True)
        self.original = voice_speaker.SPEAK_LOG
        voice_speaker.SPEAK_LOG = self.path

    def tearDown(self):
        voice_speaker.SPEAK_LOG = self.original
        self.path.unlink(missing_ok=True)

    def test_log_is_private_to_the_user(self):
        voice_speaker.log("hello")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_log_does_not_follow_a_symlink(self):
        target = self.path.with_suffix(".target")
        target.write_text("")
        try:
            self.path.symlink_to(target)
            voice_speaker.log("hello")
            self.assertEqual(target.read_text(), "")
        finally:
            target.unlink(missing_ok=True)

    def test_spoken_text_is_not_logged(self):
        with mock.patch.object(voice_speaker, "run_player"), \
                mock.patch.object(voice_speaker.shutil, "which", return_value="/usr/bin/say"):
            voice_speaker.speak("my secret plan")
        self.assertNotIn("secret", self.path.read_text())


class TestBackends(unittest.TestCase):
    def test_auto_picks_say_when_present(self):
        with mock.patch.object(voice_speaker.shutil, "which", return_value="/usr/bin/say"):
            self.assertEqual(voice_speaker.resolve_backend_name("auto"), "say")

    def test_auto_picks_espeak_without_say(self):
        with mock.patch.object(voice_speaker.shutil, "which", return_value=None):
            self.assertEqual(voice_speaker.resolve_backend_name("auto"), "espeak-ng")

    def test_explicit_backend_is_kept(self):
        self.assertEqual(voice_speaker.resolve_backend_name("gemini"), "gemini")

    def test_say_argv_guards_leading_dash(self):
        with mock.patch.object(voice_speaker.shutil, "which", return_value="/usr/bin/say"):
            utterance = voice_speaker.prepare("say", "-rf all", "", 165)
        self.assertEqual(utterance.argv[-2:], ["--", "-rf all"])

    def test_cloud_without_key_falls_back_to_local(self):
        """A missing API key must degrade to the local voice, not to silence."""
        env = {"ZRB_VOICE_BACKEND": "openai"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(voice_speaker.shutil, "which", return_value="/usr/bin/x"), \
                mock.patch.object(voice_speaker, "run_player") as player:
            voice_speaker.speak("fallback please")
        argv = player.call_args[0][0]
        self.assertEqual(argv[0], "say")
        self.assertNotIn("alloy", argv, "fallback must not inherit the cloud voice")

    def test_gemini_pcm_is_wrapped_as_wav(self):
        reply = json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000",
            "data": "AAAAAA==",
        }}]}}]}).encode()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}), \
                mock.patch.object(voice_speaker.urllib.request, "urlopen") as urlopen, \
                mock.patch.object(voice_speaker.shutil, "which", return_value="/usr/bin/afplay"):
            urlopen.return_value.__enter__.return_value.read.return_value = reply
            utterance = voice_speaker.prepare("gemini", "hi", "Sulafat", 165)
        try:
            self.assertTrue(Path(utterance.temp_path).read_bytes().startswith(b"RIFF"))
        finally:
            utterance.cleanup()
        self.assertFalse(Path(utterance.temp_path).exists(), "temp WAV must be deleted")

    def test_no_wav_player_leaves_no_temp_file(self):
        reply = json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {
            "data": "AAAAAA==",
        }}]}}]}).encode()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}), \
                mock.patch.object(voice_speaker.urllib.request, "urlopen") as urlopen, \
                mock.patch.object(voice_speaker.tempfile, "tempdir", tmp), \
                mock.patch.object(voice_speaker.shutil, "which", return_value=None):
            urlopen.return_value.__enter__.return_value.read.return_value = reply
            with self.assertRaisesRegex(RuntimeError, "no WAV player"):
                voice_speaker.prepare("gemini", "hi", "Sulafat", 165)
            self.assertEqual(os.listdir(tmp), [])


class TestHookContract(unittest.TestCase):
    """The hook must never signal anything back to zrb."""

    def _run(self, event, payload):
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": event}), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                mock.patch.object(hook_speak, "speak") as speak_mock:
            code = hook_speak.main()
        return code, speak_mock

    def test_stop_speaks_the_response(self):
        code, speak_mock = self._run(
            "Stop", {"hook_event_name": "Stop", "last_assistant_message": "All tests pass."}
        )
        self.assertEqual(code, 0, "hook must exit 0 or zrb re-runs the turn")
        self.assertIn("All tests pass", speak_mock.call_args[0][0])

    def test_stop_speaks_a_response_over_the_env_limit(self):
        """stdin has no 16 KiB cap, unlike CLAUDE_EVENT_DATA."""
        long_text = "All tests pass. " + "x" * 20000
        code, speak_mock = self._run(
            "Stop", {"hook_event_name": "Stop", "last_assistant_message": long_text}
        )
        self.assertEqual(code, 0)
        speak_mock.assert_called_once()

    def test_stop_without_message_is_silent(self):
        code, speak_mock = self._run("Stop", {"hook_event_name": "Stop"})
        self.assertEqual(code, 0)
        speak_mock.assert_not_called()

    def test_permission_request_speaks_approval(self):
        code, speak_mock = self._run(
            "PermissionRequest",
            {"tool_name": "Write", "tool_input": {"path": "/tmp/x.py"}},
        )
        self.assertEqual(code, 0)
        said = speak_mock.call_args[0][0]
        self.assertIn("approval", said.lower())
        self.assertIn("/tmp/x.py", said)

    def test_permission_request_unknown_tool_still_speaks(self):
        code, speak_mock = self._run(
            "PermissionRequest", {"tool_name": "SomeNewTool", "tool_input": {}}
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
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": "Stop"}), \
                mock.patch.object(sys, "stdin", io.StringIO("{not json")):
            self.assertEqual(hook_speak.main(), 0)

    def test_empty_stdin_exits_clean(self):
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": "Stop"}), \
                mock.patch.object(sys, "stdin", io.StringIO("")):
            self.assertEqual(hook_speak.main(), 0)

    def test_unknown_event_is_ignored(self):
        code, speak_mock = self._run("SessionStart", {"source": "startup"})
        self.assertEqual(code, 0)
        speak_mock.assert_not_called()

    def test_handler_exception_still_exits_zero(self):
        with mock.patch.dict(os.environ, {"CLAUDE_HOOK_EVENT": "Stop"}), \
                mock.patch.object(
                    sys, "stdin", io.StringIO('{"last_assistant_message": "hi"}')
                ), \
                mock.patch.object(
                    hook_speak, "handle_stop", side_effect=RuntimeError("boom")
                ):
            self.assertEqual(hook_speak.main(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
