# Voice interaction

Make zrb speak. Every response, every approval prompt, every question waiting
for an answer — read aloud.

It is a **hook**, not a change to zrb core: three `command` hooks wired to
`Stop`, `PermissionRequest` and `Notification`, plus a small speaker module.

```bash
cp hooks.json.example ~/.zrb/hooks.json     # or merge into your existing one
# then edit: replace <ZRB_REPO> with the absolute path of your checkout
```

> If you already have `~/.zrb/hooks.json` (e.g. for `grit`), **merge** the
> `hooks` block rather than overwriting the file.

The bare `python3` in the command is intentional — the hook imports nothing from
zrb, so any interpreter works. If you wire up the Gemini backend you *will* need
zrb's own interpreter instead (see "Backends").

## Files

| File | Role |
|---|---|
| `hook_speak.py` | Hook entry point. Reads the event, decides what to say. |
| `voice_speaker.py` | Cleanup, truncation, serialized playback. |
| `llm_summary.py` | Opt-in LLM summarizer (off by default). |
| `hooks.json.example` | Config to copy into `~/.zrb/hooks.json`. |
| `test_voice_interaction.py` | 25 unit tests, no dependencies. |
| `test_concurrency.py` | Proves utterances don't overlap. |

## Why this is safe to install

A `Stop` hook that misbehaves can make zrb **re-run the whole turn**: on exit 2
it injects the stderr text as a new prompt and regenerates the answer
(`session_extension.py`, `STOP_HOOK_BLOCK_CAP = 8`). Two things prevent that:

1. **`"async": true`** in the config. Verified against zrb 3.0.0: an async
   command hook is spawned fire-and-forget and *cannot* return a block. The
   drop-in proof is in "Verification" below — omit `async` and the same hook
   reports `blocked=True`.
2. **`|| exit 0`** and a `main()` that always returns 0. Belt and braces; a
   backend crash still exits clean.

The script also writes **nothing** to stdout or stderr. On `Stop`, stdout is
parsed as the JSON control protocol; on exit 2, stderr *is* the block reason.
Diagnostics go to `/tmp/zrb-voice-speaker.log`.

## The one thing that surprised me

zrb delivers the event payload in **`CLAUDE_EVENT_DATA`**, not on stdin:

```
stdin              = {"session_id": null, "cwd": "/tmp", "hook_event_name": "Stop", ...}
CLAUDE_EVENT_DATA  = {"output": "the actual assistant response"}
```

stdin carries only the Claude Code envelope. A hook that reads stdin alone —
which is what peon-ping and most Claude hooks do — finds **no `output` and
speaks nothing, silently**. This was a real bug in the first version of this
code; `TestPayloadChannels` is the regression guard.

Values over 16 KiB are dropped from the environment (`creator.py`,
`_MAX_HOOK_ENV_BYTES`), so a very long response arrives truncated. That means a
shorter utterance, never an error.

## Configuration

All via environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `ZRB_VOICE_BACKEND` | `espeak-ng` | `espeak-ng` or `gemini` |
| `ZRB_VOICE_SUMMARY` | `clean` | `clean` (deterministic) or `llm` |
| `ZRB_VOICE_MAX_CHARS` | `400` | Speech budget before truncation |
| `ZRB_VOICE_NAME` | `en-us+m3` | espeak-ng voice |
| `ZRB_VOICE_RATE` | `165` | Words per minute |
| `ZRB_VOICE_LOCK_TIMEOUT` | `30` | Max seconds to wait for the audio device |
| `ZRB_VOICE_LOG` | `/tmp/zrb-voice-speaker.log` | Side log |
| `ZRB_VOICE_SUMMARY_MODEL` | `$ZRB_LLM_MODEL` | Model for `ZRB_VOICE_SUMMARY=llm` |

### Backends

**`espeak-ng`** (default) — installed, offline, instant, robotic.

**`gemini`** — real speech quality. `zrb_extras` **is** installed in zrb's pipx
venv (`~/.local/pipx/venvs/zrb`), but note it is *not* importable from the
system `python3`. Wire it up with:

```bash
$(dirname $(readlink -f $(which zrb)))/python3 -m pip install 'zrb-extras[google-genai]'
```

(On this machine that resolves to `~/.local/pipx/venvs/zrb/bin/python3`.)

`_speak_gemini` is a **stub** — it raises `NotImplementedError` deliberately, so
a half-finished backend can't pretend to work. Implement it against
`zrb_extras.llm.tool.create_speak_tool` when you want it.

**If you enable the Gemini backend, point the hook command at zrb's own
interpreter** — the system `python3` cannot import `zrb_extras`. The default
hook needs no zrb imports, so bare `python3` is fine for espeak-ng.

## What gets said

**`Stop`** — the response, cleaned. Fenced code blocks, tables, URLs, headings,
backticks, bullets and emoji are stripped; links keep their label; truncation
prefers a sentence boundary. `nested_run` is skipped so sub-agent chatter
isn't spoken alongside the final answer.

**`PermissionRequest`** — a template: *"I need to write a file /tmp/a.py. I
need your approval."* Deliberately mechanical. This fires while you are waiting
to approve, so an LLM round-trip here is the worst possible latency. The event
carries a raw `tool_name` + `args` dict and no rendered description, so
anything richer must be built by hand.

**`Notification`** — only `elicitation_dialog` and `permission_prompt` are
announced. zrb fires `Notification` for other things too, and speaking all of
them makes this a chatty interrupter.

## Known limitations

- **Dictation is not implemented.** Listening is a *tool the model calls*, not a
  hook — hooks cannot make zrb listen. The existing `listen` tool plus
  `to_infinite_stream` in your `zrb_init.py` is the mechanism; this feature only
  speaks. Two-way voice would need the model prompted to call `listen` after
  each turn.
- **`Stop` does not fire for one-shot `zrb llm ...` invocations** the way it
  does in the chat TUI.
- **Utterances can arrive out of order.** All three hooks are `async` and spawn
  independently; the audio lock serializes them but does not order them. In a
  live run, `PermissionRequest` was observed landing ~2s *after* `Notification`.
  If ordering matters, drop `"async": true` on the event you care about — but
  then re-read "Why this is safe to install" first, because a synchronous `Stop`
  hook *can* block and re-run the turn.
- **No barge-in.** A new utterance waits for the current one rather than cutting
  it off. Speaking queues; it does not interrupt.
- **The LLM summary adds a model call per turn** and delays you *after* the
  answer is already on screen. That's why `clean` is the default.
- **Truncation is per-utterance, not per-conversation** — two long turns queue
  two 400-char readings.
- Synchronous mode is unavailable by design; `async: true` is what makes
  blocking impossible.

## Verification

```bash
python3 test_voice_interaction.py   # 25 tests: cleanup, contract, payload channels
python3 test_concurrency.py         # 3 processes must serialize, not overlap
```

End to end through zrb's real hook loader:

```bash
ZRB_PY=~/.local/pipx/venvs/zrb/bin/python3
CLAUDE_HOOK_EVENT=Stop CLAUDE_EVENT_DATA='{"output":"All tests pass."}' \
  "$ZRB_PY" hook_speak.py </dev/null; echo "exit=$?"   # must print exit=0
```

What was confirmed on this machine:

- Cleanup turns a markdown-heavy response into `'Done. Fixed the bug in
  parse(). See the PR.'` — code fence, backticks and URL all gone.
- 3 concurrent speakers: 1.79s wall, three clean 0.5s blocks, no overlap.
- All three events (Stop, PermissionRequest, Notification) fire through the real
  loader on a single event loop, each producing its own utterance.
- `async: true` → `execute_hooks` returns 0 results (fire-and-forget).
  Omitting it → `blocked=True`, i.e. the turn would re-run.
- The hook exits 0 with empty stdout and stderr on the real loader path.

**A trap when writing your own verification:** use **one** `asyncio.run()` for
the whole scenario. Firing each event under its own `asyncio.run()` silently
drops the background tasks, because each call builds a fresh event loop. That
looks exactly like "the hook didn't fire" and costs an hour to diagnose — it
caught me while validating this.

**Not verified:** actual audible output on your speakers — `espeak-ng` was
confirmed to produce a valid 83 KB 22 kHz WAV, but nothing was played and
listened to. Run `python3 voice_speaker.py "test"` to hear it.
