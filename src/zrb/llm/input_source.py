"""Provenance for text entering an LLM chat turn."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InputProvenance:
    """Where a user turn came from and whether transcription may be unreliable."""

    channel: str
    modality: str = "text"
    transcription: bool = False

    def render(self) -> str:
        """Render the compact live-context description for this input."""
        label = self.channel
        if self.modality != "text":
            label = f"{label}/{self.modality}"
        return label


KEYBOARD_INPUT = InputProvenance("keyboard")
DICTATION_INPUT = InputProvenance(
    "microphone", modality="dictation", transcription=True
)
