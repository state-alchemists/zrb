The remaining llm/ units follow the same pattern; see source for paths.

- ambient_state · L0 — leaf helpers for ambient usage/logging.
- agent_activity · L0 — per-run activity tracking and registry.
- agent_tool_result · L0 — tool result metadata and helpers.
- config · L0 — LLM-specific config mixins (resolver, limiter settings).
- factory_resolver · L0 — merge static and factory-produced tools.
- input_source · L0 — input provenance for user turns.
- journal_index_name, journal_usage_log · L0 — journal naming and usage accounting.
- message, message_text · L0 — model message helpers and formatting.
- shell_cut · L0 — cooperative turn-cut signal for backgrounding work.
- stream_observer · L0 — event observer interfaces.
- tool_registry · L0 — shared tool registry structures.
- usage_log · L0 — prompt/lookup usage metrics.

- approval · L1 — see card.
- history_manager · L1 — see card.
- hook · L1 — see card.
- lsp · L1 — language-server helpers for code tools.
- permission · L1 — see card.
- prompt · L1 — see card.
- sandbox · L1 — filesystem sandbox and policies.
- skill · L1 — skill discovery and activation.
- snapshot · L1 — working-tree snapshots and restore.
- tool · L1 — see card.
- tool_call · L1 — see card.

- agent · L2 — see card.
- summarizer · L2 — summarization agent and helpers.

- common_tools · L3 — see card.
- custom_command · L3 — slash-command framework.
- subagent · L3 — see card.
- task · L3 — see card.

- app · L4 — web app pieces.
- camera · L4 — camera feature.
- dictation · L4 — dictation feature.
- emotion · L4 — emoji emotion rendering.
- screenshot · L4 — screenshot feature.
- speech · L4 — speech feature.
- ui · L4 — see card.
- voice · L4 — Pipecat voice registry.
