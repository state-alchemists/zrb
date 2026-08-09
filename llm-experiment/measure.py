"""Measure what the ADRs assert: prompt and tool-schema weight per preset.

Every prompt/tool size quoted in AGENTS.md and the ADRs was hand-derived once
and drifted apart from the code it described. This prints the numbers instead,
so they can be regenerated rather than transcribed.

Two prompt figures are reported per preset, and they are not interchangeable:

- **file-backed** counts only the shipped markdown sections. It is a property of
  the repo and is the number a budget should be asserted against.
- **composed** additionally includes ``system_context`` (OS, cwd, detected
  tools) and ``project_context`` (every AGENTS.md/README.md up the parent
  chain), so it changes with the machine and the working directory.

    python measure.py
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

# Measure the shipped default rather than a stripped one: the journal tools are
# part of `full`'s eager surface and leaving them off understates it.
os.environ["ZRB_LLM_JOURNAL_ENABLED"] = "true"

PRESET_SECTIONS = {
    "full": ("persona", "workflow", "examples"),
    "minimal": ("persona", "workflow"),
}
VARIANTS = {"full": None, "minimal": "minimal"}


def counter():
    """cl100k_base if tiktoken is installed, else a chars/4 estimate."""
    try:
        import tiktoken  # lazy: optional, only used for measurement

        enc = tiktoken.get_encoding("cl100k_base")
        return lambda s: len(enc.encode(s)), "cl100k_base"
    except Exception:
        return lambda s: len(s) // 4, "chars/4 (install tiktoken for exact)"


class Capture:
    """A CommonToolHost that records instead of registering."""

    def __init__(self) -> None:
        self.tools: list = []
        self.factories: list = []
        self.toolsets: list = []

    def append_tool(self, *tool) -> None:
        self.tools.extend(tool)

    def append_tool_factory(self, *factory) -> None:
        self.factories.extend(factory)

    def append_toolset_factory(self, *factory) -> None:
        self.toolsets.extend(factory)


def eager_tools(preset: str) -> list:
    """Every tool a request would carry a schema for, factories resolved."""
    os.environ["ZRB_LLM_PROFILE"] = preset
    from zrb.llm.common_tools import apply_common_tools

    host = Capture()
    apply_common_tools(host)
    resolved = list(host.tools)
    for factory in host.factories:
        try:
            produced = factory(MagicMock())
        except Exception:
            continue
        resolved.extend(produced if isinstance(produced, (list, tuple)) else [produced])
    return [t for t in resolved if t is not None]


def schema_text(tool) -> tuple[str, str]:
    """(name, the text that ships with the request) for one tool."""
    from pydantic_ai import Tool

    if not isinstance(tool, Tool):
        tool = Tool(tool)
    if getattr(tool, "defer_loading", False):
        return tool.name, ""  # only the name reaches the model until searched
    schema = getattr(tool, "_parameters_json_schema", None)
    return tool.name, f"{tool.name}\n{tool.description or ''}\n{schema or ''}"


def main() -> None:
    from zrb.llm.prompt.manager import PromptManager
    from zrb.llm.prompt.prompt import get_prompt

    count, tokenizer = counter()
    print(f"tokenizer: {tokenizer}\ncwd: {os.getcwd()}\n")

    rows = []
    for preset in ("full", "minimal"):
        os.environ["ZRB_LLM_PROFILE"] = preset
        variant = VARIANTS[preset]
        files = "".join(get_prompt(s, profile=variant) for s in PRESET_SECTIONS[preset])
        composed = PromptManager().compose_prompt()(MagicMock())

        tools = eager_tools(preset)
        pairs = [schema_text(t) for t in tools]
        eager = [(n, s) for n, s in pairs if s]
        deferred = [n for n, s in pairs if not s]
        rows.append((preset, files, composed, eager, deferred))

    head = f"{'preset':9s} {'file-backed':>22s} {'composed':>22s}"
    print(head + "\n" + "-" * len(head))
    for preset, files, composed, _, _ in rows:
        print(
            f"{preset:9s} {len(files):9,d} ch {count(files):7,d} tok"
            f" {len(composed):9,d} ch {count(composed):7,d} tok"
        )

    print(f"\n{'preset':9s} {'eager':>6s} {'deferred':>9s} {'schema tokens':>14s}")
    print("-" * 42)
    for preset, _, _, eager, deferred in rows:
        total = sum(count(s) for _, s in eager)
        print(f"{preset:9s} {len(eager):6d} {len(deferred):9d} {total:14,d}")

    full_eager = {n for n, _ in rows[0][3]}
    dropped = full_eager - {n for n, _ in rows[-1][3]}
    if dropped:
        cost = sum(count(s) for n, s in rows[0][3] if n in dropped)
        pct = 100 * cost / max(sum(count(s) for _, s in rows[0][3]), 1)
        print(f"\nminimal drops {sorted(dropped)}: {cost:,} tok ({pct:.0f}% of full)")

    print("\nper-tool schema weight (full preset), heaviest first")
    print(f"  {'tool':22s}{'tokens':>8s}{'desc ch':>9s}{'schema ch':>11s}")
    for name, text in sorted(rows[0][3], key=lambda p: -count(p[1])):
        desc, _, schema = text.partition("\n")[2].partition("\n")
        print(f"  {name:22s}{count(text):8,d}{len(desc):9,d}{len(schema):11,d}")

    print("\neager tool names")
    for preset, _, _, eager, deferred in rows:
        print(
            f"  {preset:9s} {len(eager):2d}: {', '.join(sorted(n for n, _ in eager))}"
        )
        if deferred:
            print(
                f"  {'':9s} deferred ({len(deferred)}): "
                f"{', '.join(sorted(deferred))}"
            )


if __name__ == "__main__":
    main()
