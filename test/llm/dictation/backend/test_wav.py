import wave
from io import BytesIO

from zrb.llm.dictation.backend.wav import pcm16_to_wav_bytes


def test_pcm16_to_wav_bytes_wraps_pcm_in_a_mono_16khz_wav():
    pcm = b"\x01\x00\x02\x00" * 4

    wav_bytes = pcm16_to_wav_bytes(pcm)

    assert wav_bytes.startswith(b"RIFF")
    with wave.open(BytesIO(wav_bytes), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.readframes(wav.getnframes()) == pcm
