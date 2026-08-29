"""zrb-shipped LLM tools — one module per tool family.

Deliberately NOT a re-export aggregator: `tool/code.py` calls into the agent
run loop (`AnalyzeCode` delegates to a sub-agent), so an eager package-level
re-export here would force the whole `zrb.llm.agent` package to finish
loading before this package's own `__init__` returns — and anything reached
transitively while `zrb.llm.agent` is still mid-import (e.g. a hook or tool
that needs `zrb.llm.tool` back) would hit a real circular import. Nothing in
the tree imports from this package level (checked before making it empty);
import each tool from its own module instead, e.g.
`from zrb.llm.tool.file import read_file`. `common_tools.py::_register_tools`
does exactly that, and documents why.
"""
