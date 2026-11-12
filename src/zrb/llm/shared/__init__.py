"""The vocabulary every other package in `zrb.llm` speaks.

A module lives here when the layer rule gives it no home: it carries no feature
of its own, and units on both sides of a layer boundary need it. The ambient
state a run publishes (`ambient_state`, `agent_state`, `agent_activity`,
`agent_tool_result`), the seams a higher package registers itself into
(`agent_runner`, `delegation_api`), the tool registry, the message shapes, and
the small helpers for cutting and observing a run.

Keeping them at the top of `llm/` made the package a shelf: `llm/` mixed
features — `agent/`, `tool/`, `ui/` — with these shared leaves, and a reader had
to know which was which before the import line made sense. The `config/`,
`memory/` and `util/` packages stay where they are; they are subsystems with
structure of their own, not leaves.

This package deliberately imports nothing. `from zrb.llm.shared import message`
must cost nothing beyond the module named, which is why these are at layer 0.
"""
