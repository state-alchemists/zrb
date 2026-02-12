import os
import time
from datetime import datetime
from typing import Callable, Iterable, get_args

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)
from prompt_toolkit.document import Document

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
        redirect_output_commands: list[str] = [],
        summarize_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
    ):
        from pydantic_ai.models import KnownModelName

        self._history_manager = history_manager
        self._attach_commands = attach_commands
        self._exit_commands = exit_commands
        self._info_commands = info_commands
        self._save_commands = save_commands
        self._load_commands = load_commands
        self._redirect_output_commands = redirect_output_commands
        self._summarize_commands = summarize_commands
        self._set_model_commands = set_model_commands
        self._exec_commands = exec_commands
        self._custom_commands = custom_commands

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
        # expanduser=True allows ~/path
        self._path_completer = PathCompleter(expanduser=True)
        # Cache for file listing to improve performance
        self._file_cache: list[str] | None = None
        self._file_cache_time = 0
        self._cmd_history = self._get_cmd_history()

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for the current input.

        Args:
            document: The current document being edited.
            complete_event: The completion event.

        Yields:
            Completion objects for the current input.
        """
        text_before_cursor = document.text_before_cursor.lstrip()
        word = document.get_word_before_cursor(WORD=True)

        # Check if we're typing a command
        if self._is_typing_command(text_before_cursor):
            parts = text_before_cursor.split()
            # Check if we are typing the command itself or arguments
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

        # Check for file completion with @ prefix
        if word.startswith("@"):
            path_part = word[1:]
            yield from self._get_file_completions(
                path_part,
                complete_event,
                only_files=False,
                display_meta="File Path",
            )

    def _get_cmd_history(self) -> list[str]:
        history_files = [
            os.path.expanduser("~/.bash_history"),
            os.path.expanduser("~/.zsh_history"),
        ]
        unique_cmds = {}  # Use dict to preserve order (insertion order)

        for hist_file in history_files:
            if not os.path.exists(hist_file):
                continue
            try:
                with open(hist_file, "r", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # Handle zsh timestamp format: : 1612345678:0;command
                        if line.startswith(": ") and ";" in line:
                            parts = line.split(";", 1)
                            if len(parts) == 2:
                                line = parts[1]

                        if line:
                            # Remove existing to update position to end (most recent)
                            if line in unique_cmds:
                                del unique_cmds[line]
                            unique_cmds[line] = None
            except Exception:
                pass

        return list(unique_cmds.keys())

    def _get_all_command_names(self) -> list[str]:
        """Get all command names including custom commands.

        Returns:
            List of all command names.
        """
        all_commands = (
            self._exit_commands
            + self._attach_commands
            + self._summarize_commands
            + self._info_commands
            + self._save_commands
            + self._load_commands
            + self._redirect_output_commands
            + self._set_model_commands
            + self._exec_commands
        )
        custom_command_names = [cc.command for cc in self._custom_commands]
        return all_commands + custom_command_names

    def _is_typing_command(self, text_before_cursor: str) -> bool:
        """Check if the user is typing a command.

        Args:
            text_before_cursor: The text before the cursor.

        Returns:
            True if the user is typing a command, False otherwise.
        """
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
        """Yield completions for a list of commands.

        Args:
            commands: List of command strings.
            prefix: The prefix character of the command.
            lower_word: The lowercase version of the current word.
            word: The current word being typed.
            display_meta: Display metadata string or callable that takes a command.

        Yields:
            Completion objects for the commands.
        """
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
        """Get completions for command names.

        Args:
            text_before_cursor: The text before the cursor.
            word: The current word being typed.

        Yields:
            Completion objects for command names.
        """
        lower_word = word.lower()
        prefix = text_before_cursor[0]

        # Standard commands
        yield from self._yield_command_completions(
            self._exit_commands, prefix, lower_word, word, "Exit conversation"
        )
        yield from self._yield_command_completions(
            self._attach_commands,
            prefix,
            lower_word,
            word,
            lambda cmd: f"Attach file (i.e., {cmd} <path>)",
        )
        yield from self._yield_command_completions(
            self._summarize_commands, prefix, lower_word, word, "Summarize conversation"
        )
        yield from self._yield_command_completions(
            self._info_commands, prefix, lower_word, word, "Show help"
        )
        yield from self._yield_command_completions(
            self._save_commands,
            prefix,
            lower_word,
            word,
            lambda cmd: f"Save conversation (i.e., {cmd} <name>)",
        )
        yield from self._yield_command_completions(
            self._load_commands,
            prefix,
            lower_word,
            word,
            lambda cmd: f"Load conversation (i.e., {cmd} <name>)",
        )
        yield from self._yield_command_completions(
            self._redirect_output_commands,
            prefix,
            lower_word,
            word,
            lambda cmd: f"Save last response (i.e., {cmd} <file>)",
        )
        yield from self._yield_command_completions(
            self._set_model_commands,
            prefix,
            lower_word,
            word,
            lambda cmd: f"Set Model (i.e., {cmd} <model-name>)",
        )
        yield from self._yield_command_completions(
            self._exec_commands,
            prefix,
            lower_word,
            word,
            lambda cmd: f"Execute CLI command (i.e., {cmd} <command>)",
        )

        # Custom commands
        for custom_cmd in self._custom_commands:
            if custom_cmd.command.startswith(
                prefix
            ) and custom_cmd.command.lower().startswith(lower_word):
                usage = custom_cmd.description
                yield Completion(
                    custom_cmd.command,
                    start_position=-len(word),
                    display_meta=usage,
                )

    def _is_command(self, cmd: str, cmd_list: list[str]) -> bool:
        return cmd.lower() in [c.lower() for c in cmd_list]

    def _get_exec_command_completions(self, arg_prefix: str) -> Iterable[Completion]:
        """Get completions for exec command arguments (shell command history).

        Args:
            arg_prefix: The prefix of the argument being typed.

        Yields:
            Completion objects for shell commands from history.
        """
        matches = [h for h in self._cmd_history if h.startswith(arg_prefix)]
        # Sort matches by length (shorter first) as heuristic? Or just recent?
        # Since _cmd_history is set (unique), we lose order.
        # But Python 3.7+ dicts preserve insertion order, so if we used dict keys, we kept order.
        # Let's assume _get_cmd_history returns recent last.
        # We reverse to show most recent first.
        for h in reversed(matches):
            yield Completion(
                h,
                start_position=-len(arg_prefix),
                display_meta="Shell Command",
            )

    def _get_save_command_completions(self, arg_prefix: str) -> Iterable[Completion]:
        """Get completions for save command arguments (timestamp).

        Args:
            arg_prefix: The prefix of the argument being typed.

        Yields:
            Completion objects for save command.
        """
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
        if ts.startswith(arg_prefix):
            yield Completion(
                ts,
                start_position=-len(arg_prefix),
                display_meta="Session Name",
            )

    def _get_redirect_command_completions(
        self, arg_prefix: str
    ) -> Iterable[Completion]:
        """Get completions for redirect command arguments (timestamp.txt).

        Args:
            arg_prefix: The prefix of the argument being typed.

        Yields:
            Completion objects for redirect command.
        """
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M.txt")
        if ts.startswith(arg_prefix):
            yield Completion(
                ts,
                start_position=-len(arg_prefix),
                display_meta="File Name",
            )

    def _get_set_model_completions(self, arg_prefix: str) -> Iterable[Completion]:
        """Get completions for set model command arguments (model names).

        Args:
            arg_prefix: The prefix of the argument being typed.

        Yields:
            Completion objects for model names.
        """
        yield from self._get_fuzzy_completions(
            arg_prefix,
            self._known_models,
            only_files=False,
            display_meta="Model Name",
        )

    def _get_load_command_completions(self, arg_prefix: str) -> Iterable[Completion]:
        """Get completions for load command arguments (session history).

        Args:
            arg_prefix: The prefix of the argument being typed.

        Yields:
            Completion objects for session names.
        """
        results = self._history_manager.search(arg_prefix)
        for res in results[:10]:
            yield Completion(
                res,
                start_position=-len(arg_prefix),
                display_meta="Session Name",
            )

    def _get_attach_command_completions(
        self, arg_prefix: str, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for attach command arguments (file paths).

        Args:
            arg_prefix: The prefix of the argument being typed.
            complete_event: The completion event.

        Yields:
            Completion objects for file paths.
        """
        yield from self._get_file_completions(
            arg_prefix,
            complete_event,
            only_files=True,
            display_meta="File Path",
        )

    def _get_argument_completions(
        self, text_before_cursor: str, parts: list[str], complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for command arguments.

        Args:
            text_before_cursor: The text before the cursor.
            parts: The split parts of the command.
            complete_event: The completion event.

        Yields:
            Completion objects for command arguments.
        """
        cmd = parts[0]
        arg_prefix = text_before_cursor[len(cmd) :].lstrip()

        # Custom Command Argument completion
        for custom_cmd in self._custom_commands:
            if cmd == custom_cmd.command:
                usage = custom_cmd.description
                yield Completion(
                    arg_prefix,
                    start_position=-len(arg_prefix),
                    display_meta=usage,
                )
                return

        # Exec Command: Suggest History
        if self._is_command(cmd, self._exec_commands):
            yield from self._get_exec_command_completions(arg_prefix)
            return

        # Check if we are typing the second part (argument) strictly
        if not (
            (len(parts) == 1 and text_before_cursor.endswith(" "))
            or (len(parts) == 2 and not text_before_cursor.endswith(" "))
        ):
            return

        arg_prefix = parts[1] if len(parts) == 2 else ""

        # Handle specific command argument completions
        if self._is_command(cmd, self._save_commands):
            yield from self._get_save_command_completions(arg_prefix)
        elif self._is_command(cmd, self._redirect_output_commands):
            yield from self._get_redirect_command_completions(arg_prefix)
        elif self._is_command(cmd, self._set_model_commands):
            yield from self._get_set_model_completions(arg_prefix)
        elif self._is_command(cmd, self._load_commands):
            yield from self._get_load_command_completions(arg_prefix)
        elif self._is_command(cmd, self._attach_commands):
            yield from self._get_attach_command_completions(arg_prefix, complete_event)

    def _get_file_completions(
        self,
        text: str,
        complete_event: CompleteEvent,
        only_files: bool = False,
        display_meta: str | None = None,
    ) -> Iterable[Completion]:
        # Logic:
        # - If text indicates path traversal (/, ., ~), use PathCompleter
        # - Else, check file count. If < 5000, use Fuzzy. Else use PathCompleter.

        if self._is_path_navigation(text):
            yield from self._get_path_completions(
                text, complete_event, only_files, display_meta=display_meta
            )
            return

        # Count files (cached strategy could be added here if needed)
        files = self._get_recursive_files(limit=5000)
        if len(files) < 5000:
            # Fuzzy Match
            yield from self._get_fuzzy_completions(
                text, files, only_files, display_meta=display_meta
            )
        else:
            # Fallback to PathCompleter for large repos
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
        # PathCompleter needs a document where text represents the path
        fake_document = Document(text=text, cursor_position=len(text))
        for c in self._path_completer.get_completions(fake_document, complete_event):
            if only_files:
                # Check if the completed path is a directory
                # Note: 'text' is the prefix. c.text is the completion suffix.
                # We need to reconstruct full path to check isdir
                # This is tricky with PathCompleter's internal logic.
                # A simple heuristic: if it ends with path separator, it's a dir.
                if c.text.endswith(os.sep):
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

        # Sort by score (lower is better)
        matches.sort(key=lambda x: x[0])

        # Return top 20
        for _, f in matches[:20]:
            yield Completion(f, start_position=-len(text), display_meta=display_meta)

    def _get_recursive_files(self, root: str = ".", limit: int = 5000) -> list[str]:
        now = time.time()
        if self._file_cache is not None and now - self._file_cache_time < 30:
            return self._file_cache

        # Simple walker with exclusions
        paths = []
        # Check if current dir is hidden
        cwd_is_hidden = os.path.basename(os.path.abspath(root)).startswith(".")

        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Exclude hidden directories unless root is hidden
                if not cwd_is_hidden:
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]

                # Exclude common ignores
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d not in ("node_modules", "__pycache__", "venv", ".venv")
                ]

                rel_dir = os.path.relpath(dirpath, root)
                if rel_dir == ".":
                    rel_dir = ""

                # Add directories
                for d in dirnames:
                    paths.append(os.path.join(rel_dir, d) + os.sep)
                    if len(paths) >= limit:
                        self._file_cache = paths
                        self._file_cache_time = now
                        return paths

                # Add files
                for f in filenames:
                    if not cwd_is_hidden and f.startswith("."):
                        continue
                    paths.append(os.path.join(rel_dir, f))
                    if len(paths) >= limit:
                        self._file_cache = paths
                        self._file_cache_time = now
                        return paths
        except Exception:
            pass
        self._file_cache = paths
        self._file_cache_time = now
        return paths
