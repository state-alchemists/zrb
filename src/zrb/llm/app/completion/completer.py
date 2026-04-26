import os
from typing import Any, Callable, Iterable, get_args

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)
from prompt_toolkit.document import Document

from zrb.config.config import CFG
from zrb.llm.app.completion.args import (
    complete_exec_arg,
    complete_load_arg,
    complete_redirect_arg,
    complete_save_arg,
)
from zrb.llm.app.completion.caches import (
    load_cmd_history,
    load_ollama_models,
    walk_recursive_files,
)
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.util.match import fuzzy_match


class InputCompleter(Completer):
    def __init__(
        self,
        history_manager: AnyHistoryManager,
        attach_commands: list[str] = [],
        exit_commands: list[str] = [],
        info_commands: list[str] = [],
        save_commands: list[str] = [],
        load_commands: list[str] = [],
        rewind_commands: list[str] = [],
        redirect_output_commands: list[str] = [],
        summarize_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
        custom_model_names: list[str] = [],
        show_ollama_models: bool = True,
        show_pydantic_ai_models: bool = True,
    ):
        from pydantic_ai.models import KnownModelName

        self._history_manager = history_manager
        self._attach_commands = attach_commands
        self._exit_commands = exit_commands
        self._info_commands = info_commands
        self._save_commands = save_commands
        self._load_commands = load_commands
        self._rewind_commands = rewind_commands
        self._redirect_output_commands = redirect_output_commands
        self._summarize_commands = summarize_commands
        self._set_model_commands = set_model_commands
        self._exec_commands = exec_commands
        self._custom_commands = custom_commands
        self._custom_model_names = custom_model_names
        self._show_ollama_models = show_ollama_models
        self._show_pydantic_ai_models = show_pydantic_ai_models

        try:
            self._known_models = list(get_args(KnownModelName.__value__))
        except Exception:
            self._known_models = [
                "openai:gpt-4o",
                "openai:gpt-4o-mini",
                "openai:gpt-4-turbo",
                "openai:gpt-3.5-turbo",
                "google-vertex:gemini-1.5-pro",
                "google-vertex:gemini-1.5-flash",
                "anthropic:claude-3-5-sonnet-latest",
                "mistral:mistral-large-latest",
                "ollama:llama3",
            ]
        self._path_completer = PathCompleter(expanduser=True)
        self._cmd_history = load_cmd_history()
        self._file_cache: dict[str, Any] = {}
        self._ollama_cache: dict[str, Any] = {}

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text_before_cursor = document.text_before_cursor.lstrip()
        word = document.get_word_before_cursor(WORD=True)

        if self._is_typing_command(text_before_cursor):
            parts = text_before_cursor.split()
            is_typing_command = len(parts) == 1 and not text_before_cursor.endswith(" ")
            is_typing_arg = (len(parts) == 1 and text_before_cursor.endswith(" ")) or (
                len(parts) >= 2
            )

            if is_typing_command:
                yield from self._get_command_completions(text_before_cursor, word)
            elif is_typing_arg:
                yield from self._get_argument_completions(
                    text_before_cursor, parts, complete_event
                )
            return

        # File completion with @ prefix
        if word.startswith("@"):
            path_part = word[1:]
            yield from self._get_file_completions(
                path_part,
                complete_event,
                only_files=False,
                display_meta="File Path",
            )

    def _get_all_command_names(self) -> list[str]:
        all_commands = (
            self._exit_commands
            + self._attach_commands
            + self._summarize_commands
            + self._info_commands
            + self._save_commands
            + self._load_commands
            + self._rewind_commands
            + self._redirect_output_commands
            + self._set_model_commands
            + self._exec_commands
        )
        return all_commands + [cc.command for cc in self._custom_commands]

    def _is_typing_command(self, text_before_cursor: str) -> bool:
        if not text_before_cursor:
            return False
        all_command_names = self._get_all_command_names()
        command_prefixes = {cmd[0] for cmd in all_command_names if cmd}
        return text_before_cursor[0] in command_prefixes

    def _yield_command_completions(
        self,
        commands: list[str],
        prefix: str,
        lower_word: str,
        word: str,
        display_meta: str | Callable[[str], str],
    ) -> Iterable[Completion]:
        for cmd in commands:
            if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                meta = display_meta(cmd) if callable(display_meta) else display_meta
                yield Completion(
                    cmd,
                    start_position=-len(word),
                    display_meta=meta,
                )

    def _get_command_completions(
        self, text_before_cursor: str, word: str
    ) -> Iterable[Completion]:
        lower_word = word.lower()
        prefix = text_before_cursor[0]

        # (commands_list, display_meta) pairs in display order
        groups: list[tuple[list[str], str | Callable[[str], str]]] = [
            (self._exit_commands, "Exit conversation"),
            (
                self._attach_commands,
                lambda cmd: f"Attach file (i.e., {cmd} <path>)",
            ),
            (self._summarize_commands, "Summarize conversation"),
            (self._info_commands, "Show help"),
            (
                self._save_commands,
                lambda cmd: f"Save conversation (i.e., {cmd} <name>)",
            ),
            (
                self._load_commands,
                lambda cmd: f"Load conversation (i.e., {cmd} <name>)",
            ),
            (
                self._rewind_commands,
                lambda cmd: f"List or restore snapshots (i.e., {cmd} [<n>|<sha>])",
            ),
            (
                self._redirect_output_commands,
                lambda cmd: f"Save last response (i.e., {cmd} <file>)",
            ),
            (
                self._set_model_commands,
                lambda cmd: f"Set Model (i.e., {cmd} <model-name>)",
            ),
            (
                self._exec_commands,
                lambda cmd: f"Execute CLI command (i.e., {cmd} <command>)",
            ),
        ]
        for cmds, meta in groups:
            yield from self._yield_command_completions(
                cmds, prefix, lower_word, word, meta
            )

        # Custom commands
        for custom_cmd in self._custom_commands:
            if custom_cmd.command.startswith(
                prefix
            ) and custom_cmd.command.lower().startswith(lower_word):
                yield Completion(
                    custom_cmd.command,
                    start_position=-len(word),
                    display_meta=custom_cmd.description,
                )

    def _is_command(self, cmd: str, cmd_list: list[str]) -> bool:
        return cmd.lower() in [c.lower() for c in cmd_list]

    def _resolve_set_model_options(self) -> list[str]:
        """Build the model-name list for `/set-model` arg completion."""
        all_models = list(self._custom_model_names)
        if self._show_pydantic_ai_models:
            all_models.extend(self._known_models)
        if self._show_ollama_models:
            all_models.extend(load_ollama_models(self._ollama_cache))
        return all_models

    def _get_argument_completions(
        self, text_before_cursor: str, parts: list[str], complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        cmd = parts[0]
        arg_prefix = text_before_cursor[len(cmd) :].lstrip()

        # Custom commands: yield a single description-only completion.
        for custom_cmd in self._custom_commands:
            if cmd == custom_cmd.command:
                yield Completion(
                    arg_prefix,
                    start_position=-len(arg_prefix),
                    display_meta=custom_cmd.description,
                )
                return

        # Exec uses full text after the command (may contain spaces) for matching.
        if self._is_command(cmd, self._exec_commands):
            yield from complete_exec_arg(arg_prefix, self._cmd_history)
            return

        # Other commands take a single token argument.
        if not (
            (len(parts) == 1 and text_before_cursor.endswith(" "))
            or (len(parts) == 2 and not text_before_cursor.endswith(" "))
        ):
            return

        single_arg = parts[1] if len(parts) == 2 else ""

        if self._is_command(cmd, self._save_commands):
            yield from complete_save_arg(single_arg, self._history_manager)
        elif self._is_command(cmd, self._redirect_output_commands):
            yield from complete_redirect_arg(single_arg)
        elif self._is_command(cmd, self._set_model_commands):
            yield from self._get_fuzzy_completions(
                single_arg,
                self._resolve_set_model_options(),
                only_files=False,
                display_meta="Model Name",
            )
        elif self._is_command(cmd, self._load_commands):
            yield from complete_load_arg(single_arg, self._history_manager)
        elif self._is_command(cmd, self._attach_commands):
            yield from self._get_file_completions(
                single_arg,
                complete_event,
                only_files=True,
                display_meta="File Path",
            )

    def _get_file_completions(
        self,
        text: str,
        complete_event: CompleteEvent,
        only_files: bool = False,
        display_meta: str | None = None,
    ) -> Iterable[Completion]:
        # If the user starts a path-style prefix, defer to PathCompleter; otherwise
        # use fuzzy matching against the recursive walk (capped for big repos).
        if self._is_path_navigation(text):
            yield from self._get_path_completions(
                text, complete_event, only_files, display_meta=display_meta
            )
            return

        files = walk_recursive_files(
            ".", CFG.LLM_MAX_COMPLETION_FILES, self._file_cache
        )
        if len(files) < CFG.LLM_MAX_COMPLETION_FILES:
            yield from self._get_fuzzy_completions(
                text, files, only_files, display_meta=display_meta
            )
        else:
            yield from self._get_path_completions(
                text, complete_event, only_files, display_meta=display_meta
            )

    def _is_path_navigation(self, text: str) -> bool:
        return text.startswith("/") or text.startswith(".") or text.startswith("~")

    def _get_path_completions(
        self,
        text: str,
        complete_event: CompleteEvent,
        only_files: bool,
        display_meta: str | None = None,
    ) -> Iterable[Completion]:
        fake_document = Document(text=text, cursor_position=len(text))
        for c in self._path_completer.get_completions(fake_document, complete_event):
            if only_files and c.text.endswith(os.sep):
                continue
            if display_meta is not None:
                yield Completion(
                    text=c.text,
                    start_position=c.start_position,
                    display=c.display,
                    display_meta=display_meta,
                    style=c.style,
                    selected_style=c.selected_style,
                )
            else:
                yield c

    def _get_fuzzy_completions(
        self,
        text: str,
        files: list[str],
        only_files: bool,
        display_meta: str | None = None,
    ) -> Iterable[Completion]:
        matches = []
        for f in files:
            if only_files and f.endswith(os.sep):
                continue
            is_match, score = fuzzy_match(f, text)
            if is_match:
                matches.append((score, f))

        matches.sort(key=lambda x: x[0])

        for _, f in matches[:20]:
            yield Completion(f, start_position=-len(text), display_meta=display_meta)
