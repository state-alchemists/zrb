# Custom LSP Server Example

This example demonstrates `lsp_manager.register_lsp_server()` — teaching zrb about Language Server Protocol servers that aren't in the built-in catalogue, so the AI assistant gets IDE-like code intelligence (go-to-definition, find-references, document symbols, diagnostics) for any language.

## Why

Zrb ships configs for 21+ servers (Python, Go, Rust, TypeScript, …), but plenty of languages aren't covered out of the box — **Zig, Nim**, Haskell, Elixir, Bash, Terraform, and many more. Rather than wait for a built-in, you register the server yourself from `zrb_init.py`.

## How It Works

`register_lsp_server(name, config)` adds an entry to a user-extensible registry that is merged over the built-in table. Once registered, the server is a first-class citizen:

| Behavior | Detail |
|---|---|
| **Auto-detection** | Reported by `LspListServers` when `command[0]` is on `PATH` (`shutil.which`) |
| **File matching** | A file whose extension is in `file_extensions` resolves to this server |
| **Preference order** | The name participates in `ZRB_LLM_LSP_PREFERRED_SERVERS` and per-call `preferred_servers` |
| **Override** | Registering an existing name (e.g. `pyright`) replaces the built-in config for it |

## Quick Start

```bash
# Install a server you want to use (example: Zig's zls)
# See https://github.com/zigtools/zls

cd examples/lsp-config
zrb llm chat
```

Then ask:

```
What LSP servers are available?
Show me all symbols in main.zig
Where is the `parseConfig` function defined?
```

## Code

```python
from zrb.llm.lsp.configs import LSPServerConfig
from zrb.llm.lsp.manager import lsp_manager

lsp_manager.register_lsp_server(
    "zls",
    LSPServerConfig(
        name="zls",
        command=["zls"],            # must be on PATH for auto-detection
        language_ids=["zig"],       # LSP language identifiers
        file_extensions=[".zig"],   # files this server handles
    ),
)
```

`LSPServerConfig` fields:

| Field | Meaning |
|---|---|
| `name` | Display/lookup name (match the registry key) |
| `command` | How to launch the server; `command[0]` is what `which` looks for |
| `language_ids` | LSP language identifiers advertised to the server |
| `file_extensions` | Extensions (with leading dot) this server handles |

## Customization

**Pick which server wins when several match a language** — set an ordered preference list:

```bash
export ZRB_LLM_LSP_PREFERRED_SERVERS="zls,pyright,gopls"
```

Names that don't match a given file are skipped, so one flat list can span languages.

**Register at startup** — call `register_lsp_server()` once in `zrb_init.py`, before the first LSP query.

## See Also

- [`docs/advanced-topics/lsp-support.md`](../../docs/advanced-topics/lsp-support.md) — full LSP guide, including [Custom LSP Servers](../../docs/advanced-topics/lsp-support.md#custom-lsp-servers)
- `src/zrb/llm/lsp/configs.py` — the built-in `LSP_SERVER_CONFIGS` catalogue and the registry
- `src/zrb/llm/lsp/manager/manager.py` — `lsp_manager.register_lsp_server()`
