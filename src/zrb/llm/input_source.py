"""Provenance for text entering an LLM chat turn."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InputProvenance:
    """Where a user turn came from, whether transcription may be unreliable,
    and the tone it was said in when dictation heard one (*tone_score*: how
    sure, 0-1)."""

    channel: str
    modality: str = "text"
    transcription: bool = False
    tone: str = ""
    tone_score: float = 0.0

    def render(self) -> str:
        """Render the compact live-context description for this input."""
        label = self.channel
        if self.modality != "text":
            label = f"{label}/{self.modality}"
        if self.tone:
            label = f"{label}, sounding {self.tone} ({self.tone_score:.2f})"
        return label


KEYBOARD_INPUT = InputProvenance("keyboard")
WEB_INPUT = InputProvenance("web")
DICTATION_INPUT = InputProvenance(
    "microphone", modality="dictation", transcription=True
)
