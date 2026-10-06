from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.handler import ToolPolicy

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput

# Plain-substring check, so even quoted occurrences require approval. "&"
# covers "&&"; "\n"/"\r" catch multi-command payloads.
_DANGEROUS_SUBSTRINGS = (">", "|", ";", "&", "`", "$(", "\n", "\r")

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
            return True

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
