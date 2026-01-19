from typing import Iterable

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)
from prompt_toolkit.document import Document
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


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
    ):
        self._history_manager = history_manager
        self._attach_commands = attach_commands
        self._exit_commands = exit_commands
        self._info_commands = info_commands
        self._save_commands = save_commands
        self._load_commands = load_commands
        self._redirect_output_commands = redirect_output_commands
        self._summarize_commands = summarize_commands
        # expanduser=True allows ~/path
        self._path_completer = PathCompleter(expanduser=True)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        # Extract the full word before cursor (split by whitespace)
        word = document.get_word_before_cursor(WORD=True)

        # 1. Command Completion (/)
        if word.startswith("/"):
            lower_word = word.lower()
            for cmd in (
                self._exit_commands
                + self._attach_commands
                + self._summarize_commands
                + self._info_commands
                + self._save_commands
                + self._load_commands
                + self._redirect_output_commands
            ):
                if cmd.lower().startswith(lower_word):
                    # yield match
                    yield Completion(cmd, start_position=-len(word))
            return

        # 2. File Completion (@)
        if word.startswith("@"):
            # Content after '@'
            path_part = word[1:]

            # Create a virtual document for PathCompleter
            # PathCompleter needs a document where the text represents the path
            fake_document = Document(text=path_part, cursor_position=len(path_part))

            # Delegate to PathCompleter
            for c in self._path_completer.get_completions(fake_document, complete_event):
                yield c
