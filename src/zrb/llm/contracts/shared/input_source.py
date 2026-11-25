"""Provenance for text entering an LLM chat turn."""

from dataclasses import dataclass

from zrb.util.todo.duration import format_duration


@dataclass(frozen=True, slots=True)
class InputProvenance:
    """Where a user turn came from, whether transcription may be unreliable,
    the tone it was said in when dictation heard one (*tone_score*: how
    sure, 0-1), and what the microphone heard around it: how long the
    utterance lasted, whether any of it was said over a reply
    (``is_over_speech``), and whether it was said over one long enough to
    pause it (``is_barge_in``). ``idle_seconds`` is the other half of the same
    question — how long the chat had been quiet before the turn arrived."""

    channel: str
    modality: str = "text"
    transcription: bool = False
    tone: str = ""
    tone_score: float = 0.0
    spoken_seconds: float = 0.0
    is_barge_in: bool = False
    is_over_speech: bool = False
    idle_seconds: float = 0.0

    def render(self) -> str:
        """Render the compact live-context description for this input."""
        label = self.channel
        if self.modality != "text":
            label = f"{label}/{self.modality}"
        if self.tone:
            label = f"{label}, sounding {self.tone} ({self.tone_score:.2f})"
        if self.spoken_seconds > 0:
            label = f"{label}, {_spoken(self.spoken_seconds)} spoken"
        if self.is_barge_in:
            label = f"{label}, talked over the reply"
        elif self.is_over_speech:
            label = f"{label}, partly over the reply"
        if self.idle_seconds >= 1:
            label = (
                f"{label}, after {format_duration(int(self.idle_seconds))} of silence"
            )
        return label


def _spoken(seconds: float) -> str:
    """`6.4s`, `1m14s` — a dictated utterance is seconds long, so the tenth of
    a second stays useful until it runs past a minute."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    return format_duration(int(seconds))


KEYBOARD_INPUT = InputProvenance("keyboard")
WEB_INPUT = InputProvenance("web")
# Not the user's words: a background command reporting that it ended.
BACKGROUND_INPUT = InputProvenance("background process")
DICTATION_INPUT = InputProvenance(
    "microphone", modality="dictation", transcription=True
)

_USER_CHANNELS = frozenset(
    source.channel for source in (KEYBOARD_INPUT, WEB_INPUT, DICTATION_INPUT)
)


def is_user_input(source: "InputProvenance | None") -> bool:
    """Whether *source* is the user's own words, not something arriving for them.

    Compared by channel, not by identity: a dictated turn carries the microphone's
    channel with that utterance's tone, length and barge-in filled in, so it is
    never the constant itself. A sub-agent's message carries no provenance at all
    and a background command's notice names itself; anything unrecognised counts
    as not the user's, so a new source has to say where it comes from before it
    may speak for them.
    """
    return source is not None and source.channel in _USER_CHANNELS
