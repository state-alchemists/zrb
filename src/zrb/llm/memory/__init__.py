"""zrb's memory: one claim per file, a diary, a log, and a rendered core.

The package is a leaf. It imports `zrb.config` and `zrb.util`, never `zrb.llm.tool`
or `zrb.llm.prompt`, so the tools, the injected block and the reviewer can all
depend on it without closing a package cycle.
"""
