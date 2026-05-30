from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.run.openai_patch import patch_openai_model_response_serialization


def test_patch_openai_model_response_serialization_execution():
    # This ensures the function is called and coverage is recorded.
    # It also tests that it doesn't crash even if pydantic_ai is missing or different.
    patch_openai_model_response_serialization()


def test_patch_openai_model_response_serialization_logic():
    # Test the internal logic by mocking the pydantic_ai structures
    mock_context_cls = MagicMock()

    with patch("pydantic_ai.models.openai.OpenAIChatModel") as mock_model:
        mock_model._MapModelResponseContext = mock_context_cls
        patch_openai_model_response_serialization()

        # Verify it was patched
        assert mock_context_cls._into_message_param is not None

        # Test the patched function
        patched_fn = mock_context_cls._into_message_param

        # Case 1: Tool calls only -> NO content field
        self_mock = MagicMock()
        self_mock.thinkings = {}
        self_mock.texts = []
        self_mock.tool_calls = ["call1"]
        res = patched_fn(self_mock)
        assert "content" not in res
        assert res["tool_calls"] == ["call1"]

        # Case 2: Text only -> content field set
        self_mock.thinkings = {}
        self_mock.texts = ["hello"]
        self_mock.tool_calls = []
        res = patched_fn(self_mock)
        assert res["content"] == "hello"

        # Case 3: Empty -> content is None
        self_mock.thinkings = {}
        self_mock.texts = []
        self_mock.tool_calls = []
        res = patched_fn(self_mock)
        assert res["content"] is None

        # Case 4: Thinkings present
        self_mock.thinkings = {"reasoning": ["thought"]}
        self_mock.texts = []
        self_mock.tool_calls = []
        res = patched_fn(self_mock)
        assert res["reasoning"] == "thought"
        assert "content" not in res
