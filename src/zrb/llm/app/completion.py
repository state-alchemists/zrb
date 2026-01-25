import os
import time
from datetime import datetime
from typing import Iterable

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
        exec_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
    ):
        self._history_manager = history_manager
        self._attach_commands = attach_commands
        self._exit_commands = exit_commands
        self._info_commands = info_commands
        self._save_commands = save_commands
        self._load_commands = load_commands
        self._redirect_output_commands = redirect_output_commands
        self._summarize_commands = summarize_commands
        self._exec_commands = exec_commands
        self._custom_commands = custom_commands
        # expanduser=True allows ~/path
        self._path_completer = PathCompleter(expanduser=True)
        # Cache for file listing to improve performance
        self._file_cache: list[str] | None = None
        self._file_cache_time = 0
        self._cmd_history = self._get_cmd_history()

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text_before_cursor = document.text_before_cursor.lstrip()
        word = document.get_word_before_cursor(WORD=True)

        all_commands = (
            self._exit_commands
            + self._attach_commands
            + self._summarize_commands
            + self._info_commands
            + self._save_commands
            + self._load_commands
            + self._redirect_output_commands
            + self._exec_commands
        )
        custom_command_names = [cc.command for cc in self._custom_commands]
        all_command_names = all_commands + custom_command_names
        command_prefixes = {cmd[0] for cmd in all_command_names if cmd}

        # 1. Command and Argument Completion
        if text_before_cursor and text_before_cursor[0] in command_prefixes:
            parts = text_before_cursor.split()
            # Check if we are typing the command itself or arguments
            is_typing_command = len(parts) == 1 and not text_before_cursor.endswith(" ")
            is_typing_arg = (len(parts) == 1 and text_before_cursor.endswith(" ")) or (
                len(parts) >= 2
            )

            if is_typing_command:
                lower_word = word.lower()
                prefix = text_before_cursor[0]
                # Standard commands
                for cmd in self._exit_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta="Exit conversation",
                        )
                for cmd in self._attach_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta=f"Attach file (i.e., {cmd} <path>)",
                        )
                for cmd in self._summarize_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta="Summarize conversation",
                        )
                for cmd in self._info_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd, start_position=-len(word), display_meta="Show help"
                        )
                for cmd in self._save_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta=f"Save conversation (i.e., {cmd} <name>)",
                        )
                for cmd in self._load_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta=f"Load conversation (i.e., {cmd} <name>)",
                        )
                for cmd in self._redirect_output_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta=f"Save last response (i.e., {cmd} <file>)",
                        )
                for cmd in self._exec_commands:
                    if cmd.startswith(prefix) and cmd.lower().startswith(lower_word):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display_meta=f"Execute CLI command (i.e., {cmd} <command>)",
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
                return

            if is_typing_arg:
                cmd = parts[0]
                arg_prefix = text_before_cursor[len(cmd) :].lstrip()

                # Custom Command Argument completion
                for custom_cmd in self._custom_commands:
                    if cmd == custom_cmd.command:
                        usage = custom_cmd.description
                        # We don't have specific arg completion for custom commands yet,
                        # but we show the usage as meta for the current word being typed
                        # Actually Task 4 says:
                        # "When user type "/init c", the autocompletion will be "/init c", with description "/init <dir>"."
                        # This means we should yield a completion that matches current word but has the usage as description.
                        yield Completion(
                            arg_prefix,
                            start_position=-len(arg_prefix),
                            display_meta=usage,
                        )
                        return

                # Exec Command: Suggest History
                if self._is_command(cmd, self._exec_commands):
                    # Filter history
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
                    return

                # Check if we are typing the second part (argument) strictly
                # (Re-evaluating logic for other commands which only take 1 arg usually)
                if not (
                    (len(parts) == 1 and text_before_cursor.endswith(" "))
                    or (len(parts) == 2 and not text_before_cursor.endswith(" "))
                ):
                    return

                arg_prefix = parts[1] if len(parts) == 2 else ""

                # Save Command: Suggest Timestamp
                if self._is_command(cmd, self._save_commands):
                    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
                    if ts.startswith(arg_prefix):
                        yield Completion(
                            ts,
                            start_position=-len(arg_prefix),
                            display_meta="Session Name",
                        )
                    return

                # Redirect Command: Suggest Timestamp.txt
                if self._is_command(cmd, self._redirect_output_commands):
                    ts = datetime.now().strftime("%Y-%m-%d-%H-%M.txt")
                    if ts.startswith(arg_prefix):
                        yield Completion(
                            ts,
                            start_position=-len(arg_prefix),
                            display_meta="File Name",
                        )
                    return

                # Load Command: Search History
                if self._is_command(cmd, self._load_commands):
                    results = self._history_manager.search(arg_prefix)
                    for res in results[:10]:
                        yield Completion(
                            res,
                            start_position=-len(arg_prefix),
                            display_meta="Session Name",
                        )
                    return

                # Attach Command: Suggest Files
                if self._is_command(cmd, self._attach_commands):
                    yield from self._get_file_completions(
                        arg_prefix,
                        complete_event,
                        only_files=True,
                        display_meta="File Path",
                    )
                    return

                # Other commands (Exit, Info, Summarize) need no completion
                return

        # 2. File Completion (@)
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

    def _is_command(self, cmd: str, cmd_list: list[str]) -> bool:
        return cmd.lower() in [c.lower() for c in cmd_list]

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
