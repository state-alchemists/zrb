"""Talk to zrb and hear it answer.

The built-in `zrb chat` already has speech and dictation (`enable_speech`,
`enable_dictation`); this file only switches speech on and adds two helper
tasks. Every knob is read when a chat session starts, so setting it here, after
zrb is imported, still applies. `setdefault` leaves a value you exported alone.
"""

from __future__ import annotations

import os

from zrb import CFG, Group, StrInput, cli, make_task
from zrb.llm.speech import Speaker, SpeechConfig

os.environ.setdefault(f"{CFG.ENV_PREFIX}_LLM_SPEECH_ENABLED", "on")

voice_group = cli.add_group(Group("voice", description="🔊 Voice interaction"))


@make_task(
    name="say",
    description="Speak text with the configured speech backend",
    input=StrInput("text", description="Text to speak", default="Hello from zrb"),
    retries=0,
    group=voice_group,
)
def say(ctx) -> None:
    Speaker(SpeechConfig().resolve()).speak(ctx.input.text)


@make_task(
    name="mic-test",
    description="Check the microphone level against the hands-free threshold",
    retries=0,
    group=voice_group,
)
def mic_test(ctx) -> str:
    """Record five seconds and report the level against the speech threshold."""
    # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
    import numpy as np
    import sounddevice as sd

    sample_rate, block_seconds = 16000, 0.1
    threshold = CFG.LLM_DICTATION_THRESHOLD
    ctx.print(f"Input: {sd.query_devices(kind='input')['name']}")
    ctx.print("Talk now for 5 seconds...")
    audio = sd.rec(sample_rate * 5, samplerate=sample_rate, channels=1)
    sd.wait()
    levels = np.sqrt(
        (audio.reshape(-1, int(sample_rate * block_seconds)) ** 2).mean(axis=1)
    )
    loud = int((levels >= threshold).sum())
    return (
        f"Peak level {levels.max():.4f}, threshold {threshold}: "
        f"{loud} of {len(levels)} blocks count as speech"
    )
