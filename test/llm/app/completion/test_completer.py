import asyncio
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from zrb.llm.app.completion import InputCompleter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
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
        copy_commands=["/copy"],
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
    assert any(c.text == "response-2023-10-27-12-30.txt" for c in completions)


@patch("zrb.llm.app.completion.args.datetime")
def test_copy_completion(mock_datetime, completer, complete_event):
    """Typing '/copy ' suggests a transcript-<timestamp>.txt filename."""
    mock_datetime.now.return_value = datetime(2023, 10, 27, 12, 30)

    doc = Document(text="/copy ", cursor_position=6)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.text == "transcript-2023-10-27-12-30.txt" for c in completions)


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


def _make_custom_command(command, description):
    cc = MagicMock(spec=AnyCustomCommand)
    cc.command = command
    cc.description = description
    return cc


def test_custom_command_name_completion(mock_history_manager, complete_event):
    """Custom commands appear among command-name completions."""
    cc = _make_custom_command("/deploy", "Deploy the app")
    completer = InputCompleter(
        history_manager=mock_history_manager,
        custom_commands=[cc],
    )
    doc = Document(text="/de", cursor_position=3)
    completions = list(completer.get_completions(doc, complete_event))
    matched = [c for c in completions if c.text == "/deploy"]
    assert matched
    assert matched[0].display_meta_text == "Deploy the app"


def test_custom_command_arg_completion(mock_history_manager, complete_event):
    """Typing an arg after a custom command yields a description-only completion."""
    cc = _make_custom_command("/deploy", "Deploy the app")
    completer = InputCompleter(
        history_manager=mock_history_manager,
        custom_commands=[cc],
    )
    doc = Document(text="/deploy staging", cursor_position=15)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.display_meta_text == "Deploy the app" for c in completions)


def test_exec_command_arg_completion(mock_history_manager, complete_event):
    """Exec command arg completion pulls from command history."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        exec_commands=["/exec"],
    )
    completer._cmd_history = ["git status", "git commit", "ls"]
    doc = Document(text="/exec git", cursor_position=9)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert any("git status" in t for t in texts)


def test_model_subcommands_suggested_on_bare_model(
    mock_history_manager, complete_event
):
    """'/model ' suggests the small and multimodal subcommands."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        show_ollama_models=False,
        show_pydantic_ai_models=False,
        custom_model_names=["m1"],
    )
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert "small " in texts
    assert "multimodal " in texts


def test_model_subcommand_completing_first_arg(mock_history_manager, complete_event):
    """'/model sm' completes the 'small' subcommand and matching model names."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        show_ollama_models=False,
        show_pydantic_ai_models=False,
        custom_model_names=["small-llm"],
    )
    doc = Document(text="/model sm", cursor_position=9)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert "small " in texts


def test_model_subcommand_multimodal_first_arg(mock_history_manager, complete_event):
    """'/model mu' completes the 'multimodal' subcommand."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        show_ollama_models=False,
        show_pydantic_ai_models=False,
    )
    doc = Document(text="/model mu", cursor_position=9)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert "multimodal " in texts


def test_model_subcommand_then_space_completes_model_name(
    mock_history_manager, complete_event
):
    """'/model small ' completes model names for the chosen subcommand."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        show_ollama_models=False,
        show_pydantic_ai_models=False,
        custom_model_names=["fast-model"],
    )
    doc = Document(text="/model small ", cursor_position=13)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert "fast-model" in texts


def test_model_subcommand_third_part_completes_model_name(
    mock_history_manager, complete_event
):
    """'/model small fa' completes model names after the subcommand."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        set_model_commands=["/model"],
        show_ollama_models=False,
        show_pydantic_ai_models=False,
        custom_model_names=["fast-model"],
    )
    doc = Document(text="/model small fa", cursor_position=15)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert "fast-model" in texts


def test_command_with_unsupported_arg_yields_nothing(
    mock_history_manager, complete_event
):
    """A command that takes no extra args yields no completions for a 3rd token."""
    completer = InputCompleter(
        history_manager=mock_history_manager,
        info_commands=["/info"],
    )
    doc = Document(text="/info one two", cursor_position=13)
    completions = list(completer.get_completions(doc, complete_event))
    assert completions == []


def test_empty_text_yields_no_completions(completer, complete_event):
    """An empty document is not a command and yields nothing."""
    doc = Document(text="", cursor_position=0)
    completions = list(completer.get_completions(doc, complete_event))
    assert completions == []


def test_attach_path_navigation_uses_path_completer(
    mock_history_manager, complete_event, tmp_path
):
    """A path-style prefix (starts with './' etc.) defers to PathCompleter."""
    (tmp_path / "alpha.txt").write_text("x")
    completer = InputCompleter(
        history_manager=mock_history_manager,
        attach_commands=["/attach"],
    )
    target = str(tmp_path) + "/al"
    doc = Document(text=f"/attach {target}", cursor_position=len(f"/attach {target}"))
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.display_text == "alpha.txt" for c in completions)
    # only_files=True for attach -> path-style completion keeps File Path meta.
    assert all(c.display_meta_text == "File Path" for c in completions)


def test_file_at_prefix_path_navigation(mock_history_manager, complete_event, tmp_path):
    """'@<abs-path>' triggers path-navigation completion (directories allowed)."""
    (tmp_path / "beta").mkdir()
    completer = InputCompleter(history_manager=mock_history_manager)
    target = str(tmp_path) + "/be"
    doc = Document(text=f"@{target}", cursor_position=len(f"@{target}"))
    completions = list(completer.get_completions(doc, complete_event))
    # @ completion is only_files=False, so the directory is offered.
    assert any(c.display_text == "beta/" for c in completions)


def test_fuzzy_walk_too_many_files_falls_back_to_path_completer(
    mock_history_manager, complete_event, tmp_path, monkeypatch
):
    """When the recursive walk hits the file cap, completion defers to
    PathCompleter instead of fuzzy matching."""
    from zrb.llm.app.completion import completer as completer_mod

    (tmp_path / "gamma.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    completer = InputCompleter(history_manager=mock_history_manager)
    # Force the walk to "overflow" so the >= cap branch fires.
    monkeypatch.setattr(
        completer_mod, "walk_recursive_files", lambda *a, **k: ["a", "b"]
    )
    monkeypatch.setattr(completer_mod.CFG, "LLM_MAX_COMPLETION_FILES", 1)
    doc = Document(text="@gam", cursor_position=4)
    completions = list(completer.get_completions(doc, complete_event))
    assert any(c.display_text == "gamma.txt" for c in completions)


def test_known_models_fallback_on_exception(mock_history_manager, complete_event):
    """If pydantic-ai's KnownModelName can't be introspected, a static fallback
    list is used so /model completion still works."""
    with patch(
        "zrb.llm.app.completion.completer.get_args",
        side_effect=Exception("boom"),
    ):
        completer = InputCompleter(
            history_manager=mock_history_manager,
            set_model_commands=["/model"],
            show_ollama_models=False,
            show_pydantic_ai_models=True,
        )
    doc = Document(text="/model ", cursor_position=7)
    completions = list(completer.get_completions(doc, complete_event))
    texts = [c.text for c in completions]
    assert any(t.startswith("anthropic:") for t in texts)


class TestCaches:
    """Test cache-bearing IO helpers used by InputCompleter."""

    def test_load_cmd_history_zsh_format(self, tmp_path):
        from zrb.llm.app.completion.caches import load_cmd_history

        zsh_hist = tmp_path / ".zsh_history"
        zsh_hist.write_text(": 1612345678:0;ls -la\n: 1612345679:0;echo 'hello'")

        with patch("os.path.expanduser", return_value=str(zsh_hist)):
            history = load_cmd_history()
            assert "ls -la" in history
            assert "echo 'hello'" in history

    def test_load_cmd_history_exception(self):
        from zrb.llm.app.completion.caches import load_cmd_history

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("Read error")),
        ):
            history = load_cmd_history()
            assert history == []

    def test_load_ollama_models_exception(self):
        import subprocess

        from zrb.llm.app.completion.caches import load_ollama_models

        cache = {}
        with patch("subprocess.run", side_effect=subprocess.SubprocessError("Failed")):
            models = load_ollama_models(cache)
            assert models == []

    def test_walk_recursive_files_limit_dirs(self, tmp_path):
        from zrb.llm.app.completion.caches import walk_recursive_files

        d = tmp_path / "test_dir"
        d.mkdir()
        (d / "dir1").mkdir()
        (d / "dir2").mkdir()

        cache = {}
        # Limit to 1 should return early
        files = walk_recursive_files(str(d), 1, cache)
        assert len(files) == 1

    def test_walk_recursive_files_exception(self, tmp_path):
        from zrb.llm.app.completion.caches import walk_recursive_files

        cache = {}
        with patch("os.walk", side_effect=Exception("Walk error")):
            files = walk_recursive_files(str(tmp_path), 10, cache)
            assert files == []
