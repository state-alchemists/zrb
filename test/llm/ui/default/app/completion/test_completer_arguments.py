from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.ui.default.app.completion import InputCompleter


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
        photo_commands=["/photo"],
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


def _make_custom_command(command, description):
    cc = MagicMock(spec=AnyCustomCommand)
    cc.command = command
    cc.description = description
    return cc


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
    completer.cmd_history = ["git status", "git commit", "ls"]
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
    from zrb.llm.ui.default.app.completion import completer as completer_mod

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
    """If pydantic-ai cannot report its known models, a static fallback list is
    used so /model completion still works."""
    with patch(
        "pydantic_ai.models.known_model_names",
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
        from zrb.llm.ui.default.app.completion.caches import load_cmd_history

        zsh_hist = tmp_path / ".zsh_history"
        zsh_hist.write_text(": 1612345678:0;ls -la\n: 1612345679:0;echo 'hello'")

        with patch("os.path.expanduser", return_value=str(zsh_hist)):
            history = load_cmd_history()
            assert "ls -la" in history
            assert "echo 'hello'" in history

    def test_load_cmd_history_exception(self):
        from zrb.llm.ui.default.app.completion.caches import load_cmd_history

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("Read error")),
        ):
            history = load_cmd_history()
            assert history == []

    def test_load_ollama_models_exception(self):
        import subprocess

        from zrb.llm.ui.default.app.completion.caches import load_ollama_models

        cache = {}
        with patch("subprocess.run", side_effect=subprocess.SubprocessError("Failed")):
            models = load_ollama_models(cache)
            assert models == []

    def test_walk_recursive_files_limit_dirs(self, tmp_path):
        from zrb.llm.ui.default.app.completion.caches import walk_recursive_files

        d = tmp_path / "test_dir"
        d.mkdir()
        (d / "dir1").mkdir()
        (d / "dir2").mkdir()

        cache = {}
        # Limit to 1 should return early
        files = walk_recursive_files(str(d), 1, cache)
        assert len(files) == 1

    def test_walk_recursive_files_exception(self, tmp_path):
        from zrb.llm.ui.default.app.completion.caches import walk_recursive_files

        cache = {}
        with patch("os.walk", side_effect=Exception("Walk error")):
            files = walk_recursive_files(str(tmp_path), 10, cache)
            assert files == []
