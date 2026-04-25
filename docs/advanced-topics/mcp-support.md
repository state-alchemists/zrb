🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > MCP Support

# MCP Support (Model Context Protocol)

Zrb's LLM agent can connect to external **MCP servers** — tools and data sources exposed via the Model Context Protocol. This lets you extend the assistant with capabilities served by third-party processes (e.g., databases, APIs, local services).

---

## Table of Contents

- [Quick Start](#quick-start)
- [Config File Format](#config-file-format)
- [Server Types](#server-types)
- [Config Discovery](#config-discovery)
- [Configuration Reference](#configuration-reference)

---

## Quick Start

Create a file called `mcp-config.json` in your project directory (or home directory):

```json
{
  "mcpServers": {
    "my-tool": {
      "command": "npx",
      "args": ["-y", "@my-org/my-mcp-server"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

That's it. The next time you run `zrb llm chat`, Zrb will automatically load this server and make its tools available to the assistant.

---

## Config File Format

The format is the same as [Claude Desktop's MCP configuration](https://modelcontextprotocol.io/docs/getting-started), so you can reuse configs directly.

```json
{
  "mcpServers": {
    "<server-name>": {
      // Stdio server (subprocess)
      "command": "node",
      "args": ["path/to/server.js"],
      "env": { "KEY": "value" }
    },
    "<another-server>": {
      // SSE server (HTTP)
      "url": "http://localhost:8080/sse"
    }
  }
}
```

Environment variable placeholders (`${VAR_NAME}`) in `command`, `args`, and `env` values are expanded at load time.

---

## Server Types

### Stdio (subprocess)

The most common type. Zrb spawns the server as a child process and communicates over stdin/stdout.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "postgres": {
      "command": "uvx",
      "args": ["mcp-server-postgres", "--connection-string", "${DATABASE_URL}"]
    }
  }
}
```

Required fields: `command`. Optional: `args`, `env`.

### SSE (HTTP Server-Sent Events)

For servers already running as an HTTP service.

```json
{
  "mcpServers": {
    "remote-tool": {
      "url": "https://my-mcp-server.example.com/sse"
    }
  }
}
```

Required fields: `url`.

---

## Config Discovery

Zrb discovers MCP configs by traversing upward from the current working directory to the home directory, loading every config file it finds. **Later files override earlier ones** for servers with the same name, so project-level configs can override user-level ones.

**Example traversal** (for cwd = `~/projects/myapp/backend`):

| Path | Loaded? |
|------|---------|
| `~/.mcp-config.json` | Yes — user-global defaults |
| `~/projects/mcp-config.json` | Yes — workspace defaults |
| `~/projects/myapp/mcp-config.json` | Yes — app-level config |
| `~/projects/myapp/backend/mcp-config.json` | Yes — service-level config (highest priority) |

> If cwd is outside the home directory, only the cwd's config file is loaded.

---

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `ZRB_MCP_CONFIG_FILE` | `mcp-config.json` | Filename to look for in each directory during traversal |
| `ZRB_LLM_MCP_MAX_RETRIES` | `3` | Max reconnect attempts per MCP server |

To change the config filename globally:

```bash
export ZRB_MCP_CONFIG_FILE=".mcp.json"
```

Or in code:

```python
from zrb.config.config import CFG
CFG.MCP_CONFIG_FILE = ".mcp.json"
```

---
