"""Voice dictation engine for the chat TUI.

Provides push-to-talk speech-to-text: open the microphone, run voice activity
detection, transcribe via a configurable backend, and return the text.

All heavy imports (sounddevice, vosk, numpy) are lazy — they are only loaded
when `VoiceEngine.start_listening()` is called, not at module import time.
"""

from zrb.llm.voice.engine import VoiceEngine

__all__ = ["VoiceEngine"]
