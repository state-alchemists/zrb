from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.dictation.backend.multimodal import (
    MultimodalDictationBackend,
    is_openai_chat_model,
    model_name,
)
from zrb.llm.dictation.backend.wav import pcm16_to_wav_bytes

RESOLVE = "zrb.llm.config.model_resolver.resolve_configured_multimodal_model"
CAPABILITIES = "zrb.llm.util.capabilities.model_capabilities"


def _resolves_to(model):
    return patch(RESOLVE, return_value=model)


def _supports_audio(value=True):
    return patch(CAPABILITIES, **{"supports_modality.return_value": value})


class TestMultimodalBackend:
    def test_name_is_multimodal(self):
        assert MultimodalDictationBackend().name == "multimodal"

    @pytest.mark.asyncio
    async def test_transcribes_through_an_agent_with_audio_attachment(self):
        backend = MultimodalDictationBackend("gemini-2.5-flash")
        with (
            _supports_audio(),
            _resolves_to("gemini:gemini-2.5-flash") as resolve,
            patch("zrb.llm.agent.create_agent", return_value="agent") as create,
            patch(
                "zrb.llm.agent.run_agent",
                new_callable=AsyncMock,
                return_value=("  hello world ", None),
            ) as run,
        ):
            first = await backend.transcribe(b"audio")
            await backend.transcribe(b"again")

        assert first == "hello world"
        resolve.assert_called_once_with("gemini-2.5-flash")
        assert create.call_args.kwargs["model"] == "gemini:gemini-2.5-flash"
        kwargs = run.call_args_list[0].kwargs
        assert kwargs["agent"] == "agent"
        (attachment,) = kwargs["attachments"]
        assert attachment.data == pcm16_to_wav_bytes(b"audio")
        assert attachment.media_type == "audio/wav"

    @pytest.mark.asyncio
    async def test_no_configured_model_raises(self):
        with _resolves_to(None):
            with pytest.raises(RuntimeError, match="LLM_MULTIMODAL_MODEL"):
                await MultimodalDictationBackend().transcribe(b"a")

    @pytest.mark.asyncio
    async def test_openai_model_rejected(self):
        with _resolves_to("openai:gpt-4o"):
            with pytest.raises(RuntimeError, match="does not accept audio"):
                await MultimodalDictationBackend().transcribe(b"a")

    @pytest.mark.asyncio
    async def test_model_without_audio_support_rejected(self):
        with _supports_audio(False) as caps, _resolves_to("gemini:text-only"):
            with pytest.raises(RuntimeError, match="does not support audio"):
                await MultimodalDictationBackend().transcribe(b"a")
        caps.supports_modality.assert_called_once_with("gemini:text-only", "audio")


class TestIsOpenAIChatModel:
    @pytest.mark.parametrize(
        "model, expected",
        [
            ("openai:gpt-4o", True),
            ("gpt-4o", True),
            ("o1-mini", True),
            ("gemini-2.5-flash", False),
            (123, False),
        ],
    )
    def test_identifies_openai_names(self, model, expected):
        assert is_openai_chat_model(model) is expected

    def test_identifies_openai_chat_model_instance(self):
        class FakeModel:
            pass

        fake_module = MagicMock()
        fake_module.OpenAIChatModel = FakeModel
        with patch.dict("sys.modules", {"pydantic_ai.models.openai": fake_module}):
            assert is_openai_chat_model(FakeModel()) is True

    def test_falls_back_to_names_without_pydantic_ai_openai(self):
        with patch.dict("sys.modules", {"pydantic_ai.models.openai": None}):
            assert is_openai_chat_model("openai:foo") is True
            assert is_openai_chat_model("bar") is False


class TestModelName:
    def test_string_is_returned_as_is(self):
        assert model_name("gpt-4o") == "gpt-4o"

    def test_model_name_attribute(self):
        assert model_name(MagicMock(model_name="the-model")) == "the-model"

    def test_falls_back_to_type_name(self):
        class NoName:
            model_name = None
            name = None

        assert model_name(NoName()) == "NoName"
