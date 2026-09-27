"""Checks for the voice-interaction example.

Run with the Python zrb is installed in, since the hooks import zrb:
    ~/.local/pipx/venvs/zrb/bin/python test_voice_interaction.py
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import zrb_init  # noqa: E402
from zrb.llm.hook.interface import HookContext  # noqa: E402
from zrb.llm.hook.types import HookEvent  # noqa: E402
from zrb_init import clean_for_speech, truncate_for_speech  # noqa: E402

zrb_init.SPEAK_LOG = Path(tempfile.gettempdir()) / "zrb-voice-test.log"

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
        cleaned = clean_for_speech(
            "Results:\n\ncol | val\n--- | :-:\na | 1\n\nAll done."
        )
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
        zrb_init.LOCK_PATH = self.tmp

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)

    def test_dispatch_reaches_player(self):
        with (
            mock.patch.dict(os.environ, {"ZRB_VOICE_BACKEND": "auto"}),
            mock.patch.object(zrb_init, "run_player") as player,
        ):
            zrb_init.speak("hello there")
        player.assert_called_once()
        argv = player.call_args[0][0]
        self.assertIn("hello there", argv[-1])

    def test_empty_text_never_reaches_player(self):
        with mock.patch.object(zrb_init, "run_player") as player:
            zrb_init.speak("")
            zrb_init.speak("```code only```")
        player.assert_not_called()

    def test_player_failure_is_swallowed(self):
        """A broken player must not raise -- the hook has to exit 0."""
        with mock.patch.object(
            zrb_init.subprocess, "run", side_effect=RuntimeError("device busy")
        ):
            zrb_init.run_player(["say", "x"], "this should not raise")

    def test_is_speaking_tracks_the_player(self):
        """The hands-free listener mutes the mic on this; it must see playback."""
        seen = []
        with mock.patch.object(
            zrb_init.subprocess,
            "run",
            side_effect=lambda *a, **k: seen.append(zrb_init.is_speaking()),
        ):
            self.assertFalse(zrb_init.is_speaking())
            zrb_init.run_player(["say", "x"])
        self.assertEqual(seen, [True], "lock must be visible during playback")
        self.assertFalse(zrb_init.is_speaking(), "and released after")

    def test_lock_is_released_after_playing(self):
        with mock.patch.object(zrb_init.subprocess, "run"):
            zrb_init.run_player(["say", "first"])
            zrb_init.run_player(["say", "second"])  # deadlocks if leaked


class TestLog(unittest.TestCase):
    def setUp(self):
        self.path = (
            Path(tempfile.gettempdir()) / f"zrb-voice-log-test-{os.getpid()}.log"
        )
        self.path.unlink(missing_ok=True)
        self.original = zrb_init.SPEAK_LOG
        zrb_init.SPEAK_LOG = self.path

    def tearDown(self):
        zrb_init.SPEAK_LOG = self.original
        self.path.unlink(missing_ok=True)

    def test_log_is_private_to_the_user(self):
        zrb_init.log("hello")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_log_does_not_follow_a_symlink(self):
        target = self.path.with_suffix(".target")
        target.write_text("")
        try:
            self.path.symlink_to(target)
            zrb_init.log("hello")
            self.assertEqual(target.read_text(), "")
        finally:
            target.unlink(missing_ok=True)

    def test_spoken_text_is_not_logged(self):
        with (
            mock.patch.object(zrb_init, "run_player"),
            mock.patch.object(zrb_init.shutil, "which", return_value="/usr/bin/say"),
        ):
            zrb_init.speak("my secret plan")
        self.assertNotIn("secret", self.path.read_text())


class TestBackends(unittest.TestCase):
    def test_auto_picks_say_when_present(self):
        with mock.patch.object(zrb_init.shutil, "which", return_value="/usr/bin/say"):
            self.assertEqual(zrb_init.resolve_backend_name("auto"), "say")

    def test_auto_picks_espeak_without_say(self):
        with mock.patch.object(zrb_init.shutil, "which", return_value=None):
            self.assertEqual(zrb_init.resolve_backend_name("auto"), "espeak-ng")

    def test_explicit_backend_is_kept(self):
        self.assertEqual(zrb_init.resolve_backend_name("gemini"), "gemini")

    def test_say_argv_guards_leading_dash(self):
        with mock.patch.object(zrb_init.shutil, "which", return_value="/usr/bin/say"):
            utterance = zrb_init.prepare("say", "-rf all", "", 165)
        self.assertEqual(utterance.argv[-2:], ["--", "-rf all"])

    def test_cloud_without_key_falls_back_to_local(self):
        """A missing API key must degrade to the local voice, not to silence."""
        env = {"ZRB_VOICE_BACKEND": "openai"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(zrb_init.shutil, "which", return_value="/usr/bin/x"),
            mock.patch.object(zrb_init, "run_player") as player,
        ):
            zrb_init.speak("fallback please")
        argv = player.call_args[0][0]
        self.assertEqual(argv[0], "say")
        self.assertNotIn("alloy", argv, "fallback must not inherit the cloud voice")

    def test_gemini_pcm_is_wrapped_as_wav(self):
        reply = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/L16;codec=pcm;rate=24000",
                                        "data": "AAAAAA==",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ).encode()
        with (
            mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}),
            mock.patch.object(zrb_init.urllib.request, "urlopen") as urlopen,
            mock.patch.object(zrb_init.shutil, "which", return_value="/usr/bin/afplay"),
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = reply
            utterance = zrb_init.prepare("gemini", "hi", "Sulafat", 165)
        try:
            self.assertTrue(Path(utterance.temp_path).read_bytes().startswith(b"RIFF"))
        finally:
            utterance.cleanup()
        self.assertFalse(Path(utterance.temp_path).exists(), "temp WAV must be deleted")

    def test_no_wav_player_leaves_no_temp_file(self):
        reply = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": "AAAAAA==",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ).encode()
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}),
            mock.patch.object(zrb_init.urllib.request, "urlopen") as urlopen,
            mock.patch.object(zrb_init.tempfile, "tempdir", tmp),
            mock.patch.object(zrb_init.shutil, "which", return_value=None),
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = reply
            with self.assertRaisesRegex(RuntimeError, "no WAV player"):
                zrb_init.prepare("gemini", "hi", "Sulafat", 165)
            self.assertEqual(os.listdir(tmp), [])


class TestSpeakingHooks(unittest.TestCase):
    """The hooks only queue speech, so a turn never waits for audio."""

    def _run(self, hook, event, event_data=None, **fields):
        context = HookContext(event=event, event_data=event_data or {}, **fields)
        with mock.patch.object(zrb_init, "say_later") as say_later:
            result = asyncio.run(hook(context))
        self.assertTrue(result.success, "a hook must never block the turn")
        self.assertFalse(result.should_stop)
        return say_later

    def test_stop_speaks_the_response(self):
        say_later = self._run(
            zrb_init.on_stop,
            HookEvent.STOP,
            last_assistant_message="All tests pass.",
        )
        say_later.assert_called_once_with("All tests pass.", summarize=True)

    def test_stop_skips_a_sub_agent_turn(self):
        say_later = self._run(
            zrb_init.on_stop,
            HookEvent.STOP,
            {"nested_run": True},
            last_assistant_message="Sub-agent findings.",
        )
        say_later.assert_not_called()

    def test_stop_without_message_is_silent(self):
        say_later = self._run(zrb_init.on_stop, HookEvent.STOP)
        say_later.assert_not_called()

    def test_permission_request_speaks_approval(self):
        say_later = self._run(
            zrb_init.on_permission_request,
            HookEvent.PERMISSION_REQUEST,
            tool_name="Write",
            tool_input={"path": "/tmp/x.py"},
        )
        said = say_later.call_args[0][0]
        self.assertIn("approval", said.lower())
        self.assertIn("/tmp/x.py", said)

    def test_permission_request_unknown_tool_still_speaks(self):
        say_later = self._run(
            zrb_init.on_permission_request,
            HookEvent.PERMISSION_REQUEST,
            tool_name="SomeNewTool",
        )
        self.assertIn("SomeNewTool", say_later.call_args[0][0])

    def test_notification_speaks_question(self):
        say_later = self._run(
            zrb_init.on_notification,
            HookEvent.NOTIFICATION,
            notification_type="elicitation_dialog",
            message="Waiting for your answer to a question",
        )
        say_later.assert_called_once_with("Waiting for your answer to a question")

    def test_notification_ignores_unactionable_types(self):
        say_later = self._run(
            zrb_init.on_notification,
            HookEvent.NOTIFICATION,
            notification_type="something_else",
            message="noise",
        )
        say_later.assert_not_called()

    def test_hooks_are_registered_for_their_events(self):
        manager = mock.Mock()
        zrb_init.register_speaking_hooks(manager)
        registered = {
            call.args[0]: call.kwargs["events"]
            for call in manager.add_hook.call_args_list
        }
        self.assertEqual(
            registered,
            {
                zrb_init.on_stop: [HookEvent.STOP],
                zrb_init.on_permission_request: [HookEvent.PERMISSION_REQUEST],
                zrb_init.on_notification: [HookEvent.NOTIFICATION],
            },
        )


class TestSpeechQueue(unittest.TestCase):
    def test_a_failing_utterance_does_not_stop_later_ones(self):
        played = []

        def speak(text):
            if text == "bad":
                raise RuntimeError("backend down")
            played.append(text)

        with mock.patch.object(zrb_init, "speak", side_effect=speak):
            for text in ("first", "bad", "last"):
                zrb_init.say_later(text)
            deadline = time.monotonic() + 5
            while len(played) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
        self.assertEqual(played, ["first", "last"], "played in order, past the error")


class TestWakeWord(unittest.TestCase):
    def test_alternative_spellings_match(self):
        wake_words = zrb_init.parse_wake_words("hi, hai, 嗨")
        for heard, command in [
            ("Hi, what time is it?", "what time is it?"),
            ("Hai, list the files.", "list the files."),
            ("嗨，现在几点？", "现在几点？"),
            ("Hai.", ""),
        ]:
            self.assertEqual(zrb_init.strip_wake_word(heard, wake_words), command)

    def test_other_words_do_not_match(self):
        wake_words = zrb_init.parse_wake_words("hi")
        for heard in ("Hide it", "What time is it?", ""):
            self.assertIsNone(zrb_init.strip_wake_word(heard, wake_words))


if __name__ == "__main__":
    unittest.main(verbosity=2)
