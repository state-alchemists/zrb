import os
from typing import TYPE_CHECKING

from zrb.builtin.llm.chat_session_cmd import (
    ADD_SUB_CMD,
    ATTACHMENT_ADD_SUB_CMD_DESC,
    ATTACHMENT_CLEAR_SUB_CMD_DESC,
    ATTACHMENT_CMD,
    ATTACHMENT_CMD_DESC,
    ATTACHMENT_SET_SUB_CMD_DESC,
    CLEAR_SUB_CMD,
    HELP_CMD,
    HELP_CMD_DESC,
    MULTILINE_END_CMD,
    MULTILINE_END_CMD_DESC,
    MULTILINE_START_CMD,
    MULTILINE_START_CMD_DESC,
    QUIT_CMD,
    QUIT_CMD_DESC,
    RUN_CLI_CMD,
    RUN_CLI_CMD_DESC,
    SAVE_CMD,
    SAVE_CMD_DESC,
    SET_SUB_CMD,
    WORKFLOW_ADD_SUB_CMD_DESC,
    WORKFLOW_CLEAR_SUB_CMD_DESC,
    WORKFLOW_CMD,
    WORKFLOW_CMD_DESC,
    WORKFLOW_SET_SUB_CMD_DESC,
    YOLO_CMD,
    YOLO_CMD_DESC,
    YOLO_SET_CMD_DESC,
    YOLO_SET_FALSE_CMD_DESC,
    YOLO_SET_TRUE_CMD_DESC,
)

if TYPE_CHECKING:
    from prompt_toolkit.completion import Completer


def get_chat_completer() -> "Completer":

    from prompt_toolkit.completion import CompleteEvent, Completer, Completion
    from prompt_toolkit.document import Document

    class ChatCompleter(Completer):

        def get_completions(self, document: Document, complete_event: CompleteEvent):
            # Slash command
            for completion in self._complete_slash_command(document):
                yield completion
            for completion in self._complete_slash_file_command(document):
                yield completion
            # Appendix
            for completion in self._complete_appendix(document):
                yield completion

        def _complete_slash_file_command(self, document: Document):
            text = document.text_before_cursor
            prefixes = []
            for cmd in ATTACHMENT_CMD:
                for subcmd in ADD_SUB_CMD:
                    prefixes.append(f"{cmd} {subcmd} ")
            for prefix in prefixes:
                if text.startswith(prefix):
                    pattern = text[len(prefix) :]
                    potential_options = self._fuzzy_path_search(pattern, dirs=False)
                    for prefixed_option in [
                        f"{prefix}{option}" for option in potential_options
                    ]:
                        yield Completion(
                            prefixed_option,
                            start_position=-len(text),
                        )

        def _complete_slash_command(self, document: Document):
            text = document.text_before_cursor
            if not text.startswith("/"):
                return
            for command, description in self._get_cmd_options().items():
                if command.lower().startswith(text.lower()):
                    yield Completion(
                        command,
                        start_position=-len(text),
                        display_meta=description,
                    )

        def _complete_appendix(self, document: Document):
            token = document.get_word_before_cursor(WORD=True)
            prefix = "@"
            if not token.startswith(prefix):
                return
            pattern = token[len(prefix) :]
            potential_options = self._fuzzy_path_search(pattern, dirs=False)
            for prefixed_option in [
                f"{prefix}{option}" for option in potential_options
            ]:
                yield Completion(
                    prefixed_option,
                    start_position=-len(token),
                )

        def _get_cmd_options(self):
            cmd_options = {}
            # Add all commands with their descriptions
            for cmd in MULTILINE_START_CMD:
                cmd_options[cmd] = MULTILINE_START_CMD_DESC
            for cmd in MULTILINE_END_CMD:
                cmd_options[cmd] = MULTILINE_END_CMD_DESC
            for cmd in QUIT_CMD:
                cmd_options[cmd] = QUIT_CMD_DESC
            for cmd in WORKFLOW_CMD:
                cmd_options[cmd] = WORKFLOW_CMD_DESC
                for subcmd in ADD_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd}"] = WORKFLOW_ADD_SUB_CMD_DESC
                for subcmd in CLEAR_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd}"] = WORKFLOW_CLEAR_SUB_CMD_DESC
                for subcmd in SET_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd}"] = WORKFLOW_SET_SUB_CMD_DESC
            for cmd in SAVE_CMD:
                cmd_options[cmd] = SAVE_CMD_DESC
            for cmd in ATTACHMENT_CMD:
                cmd_options[cmd] = ATTACHMENT_CMD_DESC
                for subcmd in ADD_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd}"] = ATTACHMENT_ADD_SUB_CMD_DESC
                for subcmd in CLEAR_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd}"] = ATTACHMENT_CLEAR_SUB_CMD_DESC
                for subcmd in SET_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd}"] = ATTACHMENT_SET_SUB_CMD_DESC
            for cmd in YOLO_CMD:
                cmd_options[cmd] = YOLO_CMD_DESC
                for subcmd in SET_SUB_CMD:
                    cmd_options[f"{cmd} {subcmd} true"] = YOLO_SET_TRUE_CMD_DESC
                    cmd_options[f"{cmd} {subcmd} false"] = YOLO_SET_FALSE_CMD_DESC
                    cmd_options[f"{cmd} {subcmd}"] = YOLO_SET_CMD_DESC
            for cmd in HELP_CMD:
                cmd_options[cmd] = HELP_CMD_DESC
            for cmd in RUN_CLI_CMD:
                cmd_options[cmd] = RUN_CLI_CMD_DESC
            return dict(sorted(cmd_options.items()))

        def _fuzzy_path_search(
            self,
            pattern: str,
            root: str | None = None,
            max_results: int = 20,
            include_hidden: bool = False,
            case_sensitive: bool = False,
            dirs: bool = True,
            files: bool = True,
        ) -> list[str]:
            """
            Return a list of filesystem paths under `root` that fuzzy-match `pattern`.
            - pattern: e.g. "./some/x" or "proj util/io"
            - include_hidden: if False skip files/dirs starting with '.'
            - dirs/files booleans let you restrict results
            - returns list of relative paths (from root), sorted best-first
            """
            search_pattern = pattern
            if root is None:
                # Determine root and adjust pattern if necessary
                expanded_pattern = os.path.expanduser(pattern)
                if os.path.isabs(expanded_pattern) or pattern.startswith("~"):
                    # For absolute paths, find the deepest existing directory
                    if os.path.isdir(expanded_pattern):
                        root = expanded_pattern
                        search_pattern = ""
                    else:
                        root = os.path.dirname(expanded_pattern)
                        while root and not os.path.isdir(root) and len(root) > 1:
                            root = os.path.dirname(root)
                        if not os.path.isdir(root):
                            root = "."  # Fallback
                            search_pattern = pattern
                        else:
                            try:
                                search_pattern = os.path.relpath(expanded_pattern, root)
                                if search_pattern == ".":
                                    search_pattern = ""
                            except ValueError:
                                search_pattern = os.path.basename(pattern)
                else:
                    root = "."
                    search_pattern = pattern
            # Normalize pattern -> tokens split on path separators or whitespace
            search_pattern = search_pattern.strip()
            if search_pattern:
                raw_tokens = [t for t in search_pattern.split(os.path.sep) if t]
            else:
                raw_tokens = []
            # prepare tokens (case)
            if not case_sensitive:
                tokens = [t.lower() for t in raw_tokens]
            else:
                tokens = raw_tokens
            # specific ignore list
            try:
                is_recursive = os.path.abspath(os.path.expanduser(root)).startswith(
                    os.path.abspath(os.getcwd())
                )
            except Exception:
                is_recursive = False
            # walk filesystem
            candidates: list[tuple[float, str]] = []
            for dirpath, dirnames, filenames in os.walk(root):
                # Filter directories
                if not include_hidden:
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                rel_dir = os.path.relpath(dirpath, root)
                # treat '.' as empty prefix
                if rel_dir == ".":
                    rel_dir = ""
                # build list of entries to test depending on files/dirs flags
                entries = []
                if dirs:
                    entries.extend([os.path.join(rel_dir, d) for d in dirnames])
                if files:
                    entries.extend([os.path.join(rel_dir, f) for f in filenames])
                if not is_recursive:
                    dirnames[:] = []
                for ent in entries:
                    # Normalize presentation: use ./ prefix for relative paths
                    display_path = ent if ent else "."
                    # Skip hidden entries unless requested (double check for rel path segments)
                    if not include_hidden:
                        if any(
                            seg.startswith(".")
                            for seg in display_path.split(os.sep)
                            if seg
                        ):
                            continue
                    cand = display_path.replace(os.sep, "/")  # unify separator
                    cand_cmp = cand if case_sensitive else cand.lower()
                    last_pos = 0
                    score = 0.0
                    matched_all = True
                    for token in tokens:
                        # try contiguous substring search first
                        idx = cand_cmp.find(token, last_pos)
                        if idx != -1:
                            # good match: reward contiguous early matches
                            score += idx  # smaller idx preferred
                            last_pos = idx + len(token)
                        else:
                            # fallback to subsequence matching
                            pos = self._find_subsequence_pos(cand_cmp, token, last_pos)
                            if pos is None:
                                matched_all = False
                                break
                            # subsequence match is less preferred than contiguous substring
                            score += pos + 0.5 * len(token)
                            last_pos = pos + len(token)
                    if matched_all:
                        # prefer shorter paths when score ties, so include length as tiebreaker
                        score += 0.01 * len(cand)
                        out = (
                            cand
                            if os.path.abspath(cand) == cand
                            else os.path.join(root, cand)
                        )
                        candidates.append((score, out))
            # sort by score then lexicographically and return top results
            candidates.sort(key=lambda x: (x[0], x[1]))
            return [p for _, p in candidates[:max_results]]

        def _find_subsequence_pos(
            self, hay: str, needle: str, start: int = 0
        ) -> int | None:
            """
            Try to locate needle in hay as a subsequence starting at `start`.
            Returns the index of the first matched character of the subsequence or None if not
            match.
            """
            if not needle:
                return start
            i = start
            j = 0
            first_pos = None
            while i < len(hay) and j < len(needle):
                if hay[i] == needle[j]:
                    if first_pos is None:
                        first_pos = i
                    j += 1
                i += 1
            return first_pos if j == len(needle) else None

    return ChatCompleter()
