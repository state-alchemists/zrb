"""LLM sandbox: filesystem containment for LLM-initiated tool calls.

The sandbox is **off by default** (see the default-off invariant in
``zrb.llm.permission``). When enabled it constrains LLM tool calls in two
layers: a Python-level filesystem gate for in-process file tools, and an
OS-level wrapper (Seatbelt on macOS, bubblewrap on Linux) for shell commands.
See ``zrb.llm.sandbox`` and docs/advanced-topics/sandbox.md.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField, colon_join, expanduser_colon_list
from zrb.util.string.conversion import to_boolean

# Directories that commonly hold credentials. Defined here (config is a leaf
# layer) so both the EnvField default and zrb.llm.sandbox can share one source
# of truth. Entries that don't exist on a machine are silently skipped at
# resolve time, so platform-specific paths are harmless cross-platform.
DEFAULT_LLM_SANDBOX_DENY_READ_PATHS: tuple[str, ...] = (
    "~/.ssh",
    "~/.aws",
    "~/.azure",
    "~/.config/gcloud",
    "~/.kube",
    "~/.gnupg",
    "~/.netrc",
    "~/.npmrc",
    "~/.pypirc",
    "~/.git-credentials",
    "~/.docker/config.json",
    "~/.config/gh",
    "~/Library/Keychains",
    "~/AppData/Roaming/gcloud",
)


class LLMSandboxMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_SANDBOX_ENABLED: str = "false"
        self.DEFAULT_LLM_SANDBOX_OS_SHELL: str = "auto"
        self.DEFAULT_LLM_SANDBOX_WRITABLE_PATHS: str = ""
        self.DEFAULT_LLM_SANDBOX_DENY_READ_PATHS: str = ":".join(
            DEFAULT_LLM_SANDBOX_DENY_READ_PATHS
        )
        self.DEFAULT_LLM_SANDBOX_FALLBACK: str = "warn"
        self.DEFAULT_LLM_SANDBOX_ALLOW_ESCAPE: str = "true"
        super().__init__()

    LLM_SANDBOX_ENABLED = EnvField(
        to_boolean,
        doc=(
            "Master switch for the LLM tool sandbox (both the Python-level "
            "filesystem gate and the OS-level shell wrapper). Off by default; "
            "deployments opt in per environment."
        ),
    )

    LLM_SANDBOX_OS_SHELL = EnvField(
        doc=(
            "OS-level shell sandboxing mode:\n"
            "- 'auto': wraps shell commands with sandbox-exec (macOS) or bwrap "
            "(Linux) when available.\n"
            "- 'off': keeps only the Python-level filesystem gate."
        ),
    )

    LLM_SANDBOX_WRITABLE_PATHS = EnvField(
        expanduser_colon_list,
        serialize=colon_join,
        doc=(
            "Colon-separated directories LLM tool calls may write to. Empty "
            "(default) means automatic: the current working directory plus the "
            "system temp directory."
        ),
    )

    LLM_SANDBOX_DENY_READ_PATHS = EnvField(
        expanduser_colon_list,
        serialize=colon_join,
        doc=(
            "Colon-separated paths LLM tool calls may never read (credential "
            "stores). Setting this replaces the built-in default list."
        ),
    )

    LLM_SANDBOX_FALLBACK = EnvField(
        doc=(
            "Behavior when no OS-level sandbox mechanism exists (Windows, or "
            "Linux without bwrap):\n"
            "- 'warn': runs the shell command unsandboxed with a visible warning.\n"
            "- 'deny': refuses to run it."
        ),
    )

    LLM_SANDBOX_ALLOW_ESCAPE = EnvField(
        to_boolean,
        doc=(
            "Whether the dangerously_skip_sandbox tool argument is honored. "
            "When false, escape requests are blocked outright. Set false for "
            "non-interactive deployments (CI) where no human reviews approvals."
        ),
    )
