import os
import re

from prompt_toolkit.completion import Completer, Completion

from zrb.builtin.llm.chat_session_cmd import (
    ATTACHMENT_CMD,
    ATTACHMENT_CMD_DESC,
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
    WORKFLOW_CMD,
    WORKFLOW_CMD_DESC,
    YOLO_CMD,
    YOLO_CMD_DESC,
)


class ChatCompleter(Completer):

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for command, description in self._get_cmd_options().items():
                if command.lower().startswith(text.lower()):
                    yield Completion(
                        command,
                        start_position=-len(text),
                        display_meta=description,
                    )
            return
        token = document.get_word_before_cursor(WORD=True)
        if token.startswith("@"):
            pattern = token[1:]
            potential_options = self._fuzzy_path_search(pattern)
            for prefixed_option in [f"@{option}" for option in potential_options]:
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
        for cmd in SAVE_CMD:
            cmd_options[f"{cmd} <file-path>"] = SAVE_CMD_DESC
        for cmd in ATTACHMENT_CMD:
            cmd_options[cmd] = ATTACHMENT_CMD_DESC
        for cmd in YOLO_CMD:
            cmd_options[cmd] = YOLO_CMD_DESC
        for cmd in HELP_CMD:
            cmd_options[cmd] = HELP_CMD_DESC
        for cmd in RUN_CLI_CMD:
            cmd_options[cmd] = RUN_CLI_CMD_DESC
        return dict(sorted(cmd_options.items()))

    def _fuzzy_path_search(
        self,
        pattern: str,
        root: str = ".",
        max_results: int = 50,
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
        # Normalize pattern -> tokens split on path separators or whitespace
        pattern = pattern.strip()
        # allow both slashes and spaces as separators for convenience
        raw_tokens = [t for t in re.split(r"[\\/ \t]+", pattern) if t and t != "."]
        if not raw_tokens:
            return []
        # prepare tokens (case)
        if not case_sensitive:
            tokens = [t.lower() for t in raw_tokens]
        else:
            tokens = raw_tokens
        # walk filesystem
        candidates: list[tuple[float, str]] = []
        for dirpath, dirnames, filenames in os.walk(root):
            # optionally filter hidden dirs in traversal (so we don't descend into them)
            if not include_hidden:
                # mutate dirnames in-place to skip hidden directories
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
            for ent in entries:
                # Normalize presentation: use ./ prefix for relative paths
                display_path = ent if ent else "."
                # Skip hidden entries unless requested
                if not include_hidden:
                    if any(
                        seg.startswith(".") for seg in display_path.split(os.sep) if seg
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
                    # format returned path as ./something (relative to root)
                    if cand.startswith("./") or cand.startswith("."):
                        out = cand
                    else:
                        out = "./" + cand if not cand.startswith("/") else cand
                    candidates.append((score, out))
        # sort by score then lexicographically and return top results
        candidates.sort(key=lambda x: (x[0], x[1]))
        return [p for _, p in candidates[:max_results]]

    def _find_subsequence_pos(
        self, hay: str, needle: str, start: int = 0
    ) -> int | None:
        """
        Try to locate needle in hay as a subsequence starting at `start`.
        Returns the index of the first matched character of the subsequence or None if not match.
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
