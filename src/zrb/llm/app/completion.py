from typing import Iterable, List
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent


class InputCompleter(Completer):
    def __init__(self, commands: List[str]):
        self.commands = commands
        # expanduser=True allows ~/path
        self.path_completer = PathCompleter(expanduser=True)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        # Extract the full word before cursor (split by whitespace)
        word = document.get_word_before_cursor(WORD=True)

        # 1. Command Completion (/)
        if word.startswith("/"):
            lower_word = word.lower()
            for cmd in self.commands:
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
            fake_document = Document(
                text=path_part,
                cursor_position=len(path_part)
            )

            # Delegate to PathCompleter
            for c in self.path_completer.get_completions(fake_document, complete_event):
                yield c
