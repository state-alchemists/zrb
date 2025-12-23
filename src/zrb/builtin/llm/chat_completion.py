from prompt_toolkit.completion import Completer, Completion

from zrb.builtin.llm.chat_session_cmd import (
    ATTACHMENT_CMD,
    HELP_CMD,
    MULTILINE_END_CMD,
    MULTILINE_START_CMD,
    QUIT_CMD,
    RUN_CLI_CMD,
    SAVE_CMD,
    WORKFLOW_CMD,
    YOLO_CMD,
)


class ChatCompleter(Completer):

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for command in self._get_cmd_options():
                if command.lower().startswith(text.lower()):
                    yield Completion(
                        command,
                        start_position=-len(text),
                    )
            return
        token = document.get_word_before_cursor(WORD=True)
        if "@" in token:
            local, _, domain = token.partition("@")
            for d in ["gmail.com", "yahoo.com", "outlook.com"]:
                if d.startswith(domain):
                    yield Completion(
                        f"{local}@{d}",
                        start_position=-len(token),
                        display_meta="domain"
                    )
        # word = document.get_word_before_cursor(WORD=True)

    def _get_cmd_options(self):
        return (
            MULTILINE_START_CMD
            + MULTILINE_END_CMD
            + QUIT_CMD
            + WORKFLOW_CMD
            + SAVE_CMD
            + ATTACHMENT_CMD
            + YOLO_CMD
            + HELP_CMD
            + RUN_CLI_CMD
        )
