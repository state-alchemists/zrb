import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import ToolPolicy, UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart

# Shell metacharacters that could indicate state-changing operations.
# Checked as plain substrings (conservative: even inside quotes triggers approval).
_DANGEROUS_SUBSTRINGS = (">", "|", ";", "&&", "`", "$(")

# Command prefixes that are always read-only (no state changes possible).
# A command is safe only if it starts with one of these prefixes (case-insensitive,
# followed by end-of-string, space, or tab) AND contains no dangerous metacharacters.
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
    "env",
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


def _is_safe_command(command: str) -> bool:
    """Return True only when the command is known read-only with no dangerous metacharacters."""
    stripped = command.strip()

    # Reject anything that contains a dangerous shell metacharacter.
    # Conservative: "when in doubt, ask" — even quoted occurrences trigger approval.
    for dangerous in _DANGEROUS_SUBSTRINGS:
        if dangerous in stripped:
            return False

    # Accept only commands beginning with a known-safe prefix.
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
    """
    Returns a ToolPolicy that auto-approves Bash tool calls whose command is
    read-only and contains no state-changing shell metacharacters.

    Uses an allowlist: only explicitly known-safe command prefixes are auto-approved.
    Everything else falls through to the next policy (user prompt).
    """

    async def _policy(
        ui: UIProtocol,
        call: "ToolCallPart",
        next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
    ) -> Any:
        from pydantic_ai import ToolApproved

        if call.tool_name != "Bash":
            return await next_handler(ui, call)

        try:
            args = call.args
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                return await next_handler(ui, call)
            command = args.get("command", "")
            if not isinstance(command, str):
                return await next_handler(ui, call)
        except (json.JSONDecodeError, ValueError):
            return await next_handler(ui, call)

        if _is_safe_command(command):
            return ToolApproved()

        return await next_handler(ui, call)

    return _policy
