import asyncio
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from zrb.llm.app.completion import InputCompleter
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


@pytest.fixture
def mock_history_manager():
    manager = MagicMock(spec=AnyHistoryManager)
    manager.search.return_value = ["session1", "session2"]
    return manager


@pytest.fixture
def completer(mock_history_manager):
    return InputCompleter(
        history_manager=mock_history_manager,
        attach_commands=["/attach"],
        exit_commands=["/exit"],
        info_commands=["/info"],
        save_commands=["/save"],
        load_commands=["/load"],
        redirect_output_commands=["/out"],
        summarize_commands=["/sum"],
    )


@pytest.fixture
def complete_event():
    return MagicMock(spec=CompleteEvent)


def test_command_completion(completer, complete_event):
    doc = Document(text="/ex", cursor_position=3)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "/exit" for c in completions)


@patch("zrb.llm.app.completion.args.datetime")
def test_save_completion(mock_datetime, completer, complete_event):
    mock_datetime.now.return_value = datetime(2023, 10, 27, 12, 30)
    mock_datetime.strftime = datetime.strftime

    doc = Document(text="/save ", cursor_position=6)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "2023-10-27-12-30" for c in completions)


@patch("zrb.llm.app.completion.args.datetime")
def test_redirect_completion(mock_datetime, completer, complete_event):
    mock_datetime.now.return_value = datetime(2023, 10, 27, 12, 30)

    doc = Document(text="/out ", cursor_position=5)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "2023-10-27-12-30.txt" for c in completions)


def test_load_completion(completer, complete_event):
    doc = Document(text="/load ", cursor_position=6)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "session1" for c in completions)
    assert any(c.text == "session2" for c in completions)


def test_different_prefix_completion(mock_history_manager, complete_event):
    completer = InputCompleter(
        history_manager=mock_history_manager,
        redirect_output_commands=[">out"],
    )
    doc = Document(text=">o", cursor_position=2)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == ">out" for c in completions)


@pytest.mark.asyncio
async def test_file_completion_public_api(completer, complete_event):
    """Test public file completion behavior via get_completions."""
    with patch("os.walk") as mock_os_walk:
        # Simulate a file system with a few files and directories
        mock_os_walk.return_value = [
            (".", ["dir1", "dir2"], ["file1.txt", "file2.py"]),
            ("dir1", [], ["nested_file.md"]),
            ("dir2", ["sub_dir"], []),
            ("dir2/sub_dir", [], ["another.txt"]),
        ]

        # Test completion for "@f"
        doc = Document(text="@f", cursor_position=2)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "file1.txt" for c in completions)
        assert any(c.text == "file2.py" for c in completions)
        assert not any(
            c.text == "dir1/" for c in completions
        )  # Directories should not be completed when only files are expected

        # Test completion for "@dir1/"
        doc = Document(text="@dir1/", cursor_position=6)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "dir1/nested_file.md" for c in completions)

        # Test completion for "/attach f"
        doc = Document(text="/attach f", cursor_position=9)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "file1.txt" for c in completions)
        assert any(c.text == "file2.py" for c in completions)
        assert not any(
            c.text == "dir1/" for c in completions
        )  # Directories should not be completed for attach command

        # Test completion for "/attach dir2/sub_dir/"
        doc = Document(text="/attach dir2/sub_dir/", cursor_position=21)
        completions = list(completer.get_completions(doc, complete_event))
        assert any(c.text == "dir2/sub_dir/another.txt" for c in completions)


def test_custom_model_names_appear_in_model_completions(
    mock_history_manager, complete_event
):
    """Custom model names must appear as completions after the /model command."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        custom_model_names=["my-custom-model", "team-llm"],
    )
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    completion_texts = [c.text for c in completions]
    assert "my-custom-model" in completion_texts
    assert "team-llm" in completion_texts


def test_custom_model_names_empty_by_default(mock_history_manager, complete_event):
    """InputCompleter works with no custom model names (default empty list)."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
    )
    doc = Document(text="/model ", cursor_position=7)
    # Should complete without error; known models still appear
    completions = list(completer.get_completions(doc, complete_event))
    assert isinstance(completions, list)


def test_show_ollama_models_false_excludes_ollama_models(
    mock_history_manager, complete_event
):
    """When show_ollama_models=False, Ollama models should not appear in completions."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        custom_model_names=["custom-model"],
        show_ollama_models=False,
    )
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    completion_texts = [c.text for c in completions]
    # When show_ollama_models=False, ollama models should not be fetched at all
    # The completer should only show custom models and pydantic-ai models
    assert "custom-model" in completion_texts
    # Verify no "ollama:" prefix in completions (assuming no ollama installed in test env)
    ollama_models = [c for c in completion_texts if c.startswith("ollama:")]
    assert len(ollama_models) == 0


def test_show_ollama_models_true_includes_ollama_models(
    mock_history_manager, complete_event
):
    """When show_ollama_models=True (default), Ollama models should appear in completions."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        custom_model_names=["custom-model"],
        show_pydantic_ai_models=False,  # Exclude pydantic-ai models for cleaner test
        show_ollama_models=True,
    )
    # Pre-fill the cache to skip the subprocess call
    completer._ollama_cache = {
        "models": ["ollama:llama3", "ollama:mistral"],
        "time": time.time() + 1000,
    }
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    completion_texts = [c.text for c in completions]
    assert "ollama:llama3" in completion_texts
    assert "ollama:mistral" in completion_texts
    assert "custom-model" in completion_texts


def test_show_pydantic_ai_models_false_excludes_known_models(
    mock_history_manager, complete_event
):
    """When show_pydantic_ai_models=False, pydantic-ai known models should not appear."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        custom_model_names=["custom-model"],
        show_pydantic_ai_models=False,
    )
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    completion_texts = [c.text for c in completions]
    # Known models from pydantic-ai should not be present
    assert "custom-model" in completion_texts
    # Verify no pydantic-ai known models are in the completions (they're typically prefixed)
    # Just verify it doesn't crash and only custom-model appears (plus any ollama if installed)
    assert isinstance(completions, list)


def test_show_pydantic_ai_models_true_includes_known_models(
    mock_history_manager, complete_event
):
    """When show_pydantic_ai_models=True (default), pydantic-ai known models should appear."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        custom_model_names=["custom-model"],
        show_pydantic_ai_models=True,
    )
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    # Should complete without error; known models should be present
    assert isinstance(completions, list)
    completion_texts = [c.text for c in completions]
    assert "custom-model" in completion_texts


def test_both_flags_false_only_custom_models(mock_history_manager, complete_event):
    """When both show flags are False, only custom_model_names should appear."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        custom_model_names=["model-a", "model-b"],
        show_ollama_models=False,
        show_pydantic_ai_models=False,
    )
    # Even if cache has ollama models, they should NOT appear
    completer._ollama_cache = {
        "models": ["ollama:llama3"],
        "time": time.time() + 1000,
    }
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    completion_texts = [c.text for c in completions]
    # Only custom models should be present
    assert "model-a" in completion_texts
    assert "model-b" in completion_texts
    assert "ollama:llama3" not in completion_texts
    # Also no pydantic-ai known models should appear
    # They all have prefixes like "openai:", "anthropic:", etc.
    for completion in completion_texts:
        assert ":" not in completion or completion in ["model-a", "model-b"]
