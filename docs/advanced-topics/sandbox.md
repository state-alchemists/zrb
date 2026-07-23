🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Sandbox

# Sandbox: Filesystem Containment for LLM Tool Calls

The [permission policy](permission-policy.md) controls **intent** — which tool
calls the user agrees to. The sandbox controls **blast radius** — what an
approved (or auto-approved) call can actually touch on disk. Both are needed:
a prompt-injected `npm install` the user rubber-stamps looks legitimate, but
under the sandbox it still cannot overwrite `~/.zshrc` or read `~/.ssh`.

The sandbox is **opt-in and off by default** (the same default-off invariant
as the permission layer): with `ZRB_LLM_SANDBOX_ENABLED` unset, every tool
behaves exactly as before.

## The Two Layers

One `SandboxPolicy` (`zrb/llm/sandbox/`) drives two enforcement layers:

1. **Python-level filesystem gate** (all platforms). `_sandbox_gate` in
   `agent/common.py` runs next to the permission gate for every tool call. It
   realpaths path-like arguments (`path`, `file_path`, `src`, `dst`, …) and
   blocks:
   - **writes** outside the writable roots for `EDIT` and `UNKNOWN`-capability
     tools (`Write`, `Edit`, `RM`, `MV`, unvetted MCP tools),
   - **reads** inside the deny-read list (credential directories such as
     `~/.ssh`, `~/.aws`, `~/.kube`) for every tool.
   A blocked call returns a `ToolReturn` with `metadata={"blocked": True}` and
   a `[SYSTEM SUGGESTION]`, so the model can adapt instead of crashing.
2. **OS-level shell wrapper** (macOS, Linux). `Shell`/`Bash` subprocesses
   (foreground or `background=True`) are spawned through a kernel-enforced
   sandbox, immune to `cd`,
   symlink tricks, and check-then-use races:
   - **macOS** — `sandbox-exec -p <generated SBPL profile>` (Seatbelt).
     Deprecated-but-functional; Chrome, Bazel, and Codex still ship on it.
   - **Linux** — `bwrap` (bubblewrap): read-only root bind, read-write binds
     for the writable roots, `tmpfs`/`/dev/null` masks over the deny-read
     paths. No PID/network unsharing, so process-group handling, timeout
     kill, and background-PID tracking keep working.

In v1 the sandbox isolates the **filesystem only** — network stays open
(commands like `git pull` and `pip install` keep working).

## Platform Matrix

| Platform | File tools (in-process) | Shell commands |
|---|---|---|
| macOS | Python FS gate | Seatbelt (`sandbox-exec`) |
| Linux | Python FS gate | bubblewrap (`bwrap`), fallback below if missing |
| Windows | Python FS gate | **No OS mechanism** — fallback below |

When no OS mechanism is available (Windows, or Linux without `bwrap`), the
policy's `fallback` mode applies — never a silent passthrough:

- `warn` (default): the command runs unsandboxed and a visible
  `[WARNING] sandbox unavailable (...)` line is prepended to the tool output.
- `deny`: the shell tool refuses with an explanatory error. Deployments that
  want hard guarantees on Windows set this and rely on the file tools plus
  approval prompts.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ZRB_LLM_SANDBOX_ENABLED` | `false` | Master switch for both layers. |
| `ZRB_LLM_SANDBOX_OS_SHELL` | `auto` | `auto` wraps shell commands when a mechanism exists; `off` keeps only the Python FS gate. |
| `ZRB_LLM_SANDBOX_WRITABLE_PATHS` | (empty) | Colon-separated writable roots. Empty = automatic: current working directory + system temp dir. |
| `ZRB_LLM_SANDBOX_DENY_READ_PATHS` | built-in list | Colon-separated never-read paths; setting it replaces the default credential-store list. |
| `ZRB_LLM_SANDBOX_FALLBACK` | `warn` | `warn` / `deny` when no OS mechanism exists. |
| `ZRB_LLM_SANDBOX_ALLOW_ESCAPE` | `true` | Whether `dangerously_skip_sandbox` is honored at all. Set `false` for non-interactive (CI) deployments. |

The default deny-read list covers `~/.ssh`, `~/.aws`, `~/.azure`,
`~/.config/gcloud`, `~/.kube`, `~/.gnupg`, `~/.netrc`, `~/.npmrc`,
`~/.pypirc`, `~/.git-credentials`, `~/.docker/config.json`, `~/.config/gh`,
`~/Library/Keychains`, and `~/AppData/Roaming/gcloud`. Entries absent on a
machine are skipped at resolve time, so the list is cross-platform-safe.

The system temp directory is **always writable**, even with explicit
`WRITABLE_PATHS` — the shell tool's PID-tracking wrapper writes a temp file
from inside the sandbox, and temp dirs are world-writable by design anyway.

Python API: both `LLMTask(..., sandbox=...)` and `LLMChatTask(..., sandbox=...)`
accept `True`/`False` (config-derived policy with `enabled` forced) or a
`SandboxPolicy` instance; `sandbox` is also a read/write property on both. Sub-agents
inherit the parent run's policy through the `current_sandbox_policy`
ContextVar, exactly like the permission policy.

## Escape Hatch

`Shell` and `Bash` (foreground or `background=True`) accept
`dangerously_skip_sandbox: bool = False`. A truthy value:

- is **never auto-approved** — `bash_safe_command_policy` and `auto_approve`
  always route it to the human prompt, no matter how read-only the command
  looks;
- is blocked outright when `ZRB_LLM_SANDBOX_ALLOW_ESCAPE=false`;
- prepends `[NOTE] executed outside the sandbox` to the tool output.

## Threat Model and Non-Goals

The sandbox contains LLM-initiated filesystem damage: prompt injection,
model mistakes, and over-broad approved commands. It is **not** a complete
security boundary in v1. Known limits, by design:

- **No network isolation** — data exfiltration over the network is not
  prevented (a later phase can add a domain-filtering proxy).
- **Python-layer TOCTOU** — the FS gate realpaths at check time; a race
  between check and `open()` is theoretically possible for in-process tools.
  The OS shell layer has no such race (kernel-enforced per syscall).
- **Windows shell gap** — no OS-level shell isolation exists; see the
  platform matrix.
- **Setuid binaries on macOS** — a Seatbelt-sandboxed process cannot exec
  set[ug]id binaries regardless of profile. Notably `/bin/ps` (setuid root)
  and `sudo` fail with `Operation not permitted`; `pgrep`/`pkill` keep
  working.
- **zrb-internal writes** (session logs, journal, snapshots) bypass the gate
  — only LLM-initiated tool calls are constrained.

See [ADR-0063](../adr/adr-0063.md) for the full design rationale.

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Sandbox
