import shlex
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from zrb.llm.tool_call.handler import ToolPolicy
from zrb.llm.util.tool_args import parse_tool_args

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput

# Plain-substring check, so even quoted occurrences require approval. "&"
# covers "&&"; "\n"/"\r" catch multi-command payloads; "<(" is process
# substitution, which runs its command just as "$(" does.
_DANGEROUS_SUBSTRINGS = (">", "|", ";", "&", "`", "$(", "<(", "\n", "\r")

# Read-only prefixes, matched case-insensitively and followed by end, space or tab.
_SAFE_PREFIXES = (
    # Git: only universally read-only subcommands
    "git status",
    "git diff",
    "git log",
    "git show",
    # File / directory listing
    "ls",
    "ll",
    "la",
    # Text output (safe without redirection, which the metachar check handles)
    "echo",
    "printf",
    "cat",
    "head",
    "tail",
    # Search
    "grep",
    "egrep",
    "fgrep",
    "rg",
    # System info
    "ps",
    "df",
    "du",
    "stat",
    "file",
    "uname",
    "hostname",
    "date",
    "whoami",
    "id",
    "groups",
    "uptime",
    # Path / environment
    "which",
    "type",
    "whereis",
    "pwd",
    # Not bare "env": `env FOO=1 rm -rf x` runs an arbitrary command.
    "printenv",
    # Count / sort (safe without redirect)
    "wc",
    "sort",
    "uniq",
    # Version queries
    "python --version",
    "python3 --version",
    "node --version",
    "npm --version",
    "pip --version",
    "pip3 --version",
    "pip show",
    "go version",
    "cargo --version",
    "rustc --version",
    "java -version",
    "java --version",
    "ruby --version",
    "docker --version",
    "kubectl version",
)

# Long options that run a program or write a file, per allowlisted command. An
# option matches by its exact name or by any prefix of it, because git and GNU
# sort/file accept unambiguous abbreviations (`git log --out=x`).
_RG_UNSAFE_LONG_OPTIONS = ("pre", "pre-glob", "hostname-bin")
_GIT_UNSAFE_LONG_OPTIONS = ("output", "ext-diff", "textconv")
_SORT_UNSAFE_LONG_OPTIONS = ("output", "compress-program")
_FILE_UNSAFE_LONG_OPTIONS = ("compile",)
_GIT_CHECKED_SUBCOMMANDS = ("diff", "log", "show")
# `uniq` long options whose value may be the next word.
_UNIQ_VALUE_LONG_OPTIONS = ("skip-fields", "skip-chars", "check-chars")


def _is_unsafe_long_option(word: str, unsafe_names: tuple[str, ...]) -> bool:
    name = word[2:].split("=", 1)[0]
    return name != "" and any(unsafe.startswith(name) for unsafe in unsafe_names)


def _has_unsafe_option(
    args: list[str],
    unsafe_long: tuple[str, ...],
    unsafe_short: str,
    short_takes_value: str,
) -> bool:
    for word in args:
        if word == "--":
            return False
        if word.startswith("--"):
            if _is_unsafe_long_option(word, unsafe_long):
                return True
        elif word.startswith("-"):
            # Short options cluster (`-uo FILE`); the first one that takes a
            # value swallows the rest of the word.
            for letter in word[1:]:
                if letter in unsafe_short:
                    return True
                if letter in short_takes_value:
                    break
    return False


def _has_uniq_output_file(args: list[str]) -> bool:
    """`uniq [OPTION]... [INPUT [OUTPUT]]`: a second positional word is written to."""
    positionals = 0
    expecting_value = False
    options_done = False
    for word in args:
        if expecting_value:
            expecting_value = False
        elif options_done or word == "-" or not word.startswith("-"):
            positionals += 1
        elif word == "--":
            options_done = True
        elif word.startswith("--"):
            name, has_value, _ = word[2:].partition("=")
            expecting_value = not has_value and any(
                option.startswith(name) for option in _UNIQ_VALUE_LONG_OPTIONS
            )
        else:
            for index, letter in enumerate(word[1:], start=1):
                if letter in "fsw":
                    expecting_value = index == len(word) - 1
                    break
    return positionals > 1


def _has_expansion_hiding_option(args: list[str]) -> bool:
    """True when a word could expand into an option the checks never see.

    The shell expands `--pr${X}e` or `${X:---pre=cmd}` after the allowlist has
    looked at the text, so such words cannot be vetted and need a human.
    """
    for word in args:
        if word == "--":
            return False
        if word.startswith(("$", "{")):
            return True
        if word.startswith("-") and ("$" in word or "{" in word):
            return True
    return False


def _has_flag_that_runs_or_writes(command: str) -> bool:
    """True when an allowlisted command carries an option that runs a program or writes a file."""
    head = command.lower().split(None, 2)
    if not head:
        return False
    name = head[0]
    if name == "git":
        if len(head) < 2 or head[1] not in _GIT_CHECKED_SUBCOMMANDS:
            return False
        skipped = 2
    elif name in ("rg", "sort", "uniq", "file"):
        skipped = 1
    else:
        return False
    try:
        args = shlex.split(command)[skipped:]
    except ValueError:
        # Unbalanced quotes: the words cannot be read reliably.
        return True
    if _has_expansion_hiding_option(args):
        return True
    if name == "rg":
        return _has_unsafe_option(args, _RG_UNSAFE_LONG_OPTIONS, "", "")
    if name == "git":
        return _has_unsafe_option(args, _GIT_UNSAFE_LONG_OPTIONS, "", "")
    if name == "sort":
        return _has_unsafe_option(args, _SORT_UNSAFE_LONG_OPTIONS, "o", "kSTt")
    if name == "file":
        return _has_unsafe_option(args, _FILE_UNSAFE_LONG_OPTIONS, "C", "fFmeP")
    return _has_uniq_output_file(args)


def is_safe_command(command: str) -> bool:
    """Return True only when the command is known read-only with no dangerous metacharacters."""
    stripped = command.strip()
    for dangerous in _DANGEROUS_SUBSTRINGS:
        if dangerous in stripped:
            return False

    lower = stripped.lower()
    for prefix in _SAFE_PREFIXES:
        if (
            lower == prefix
            or lower.startswith(prefix + " ")
            or lower.startswith(prefix + "\t")
        ):
            return not _has_flag_that_runs_or_writes(stripped)

    return False


def bash_safe_command_policy() -> ToolPolicy:
    """ToolPolicy auto-approving Shell calls whose command is on the read-only allowlist."""

    async def _policy(
        ui: "AnyAgentOutput",
        call: "ToolCallPart",
        next_handler: Callable[["AnyAgentOutput", "ToolCallPart"], Awaitable[Any]],
    ) -> Any:
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ToolApproved

        if call.tool_name != "Shell":
            return await next_handler(ui, call)

        args = parse_tool_args(call)
        if args is None:
            return await next_handler(ui, call)
        command = args.get("command", "")
        if not isinstance(command, str):
            return await next_handler(ui, call)

        # A sandbox-escape request must always reach a human.
        if args.get("dangerously_skip_sandbox"):
            return await next_handler(ui, call)

        if is_safe_command(command):
            return ToolApproved()

        return await next_handler(ui, call)

    return _policy
