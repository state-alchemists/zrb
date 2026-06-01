# #6 — Tool-output truncation with a re-fetch handle

## Problem

`create_safe_wrapper` and `SafeToolsetWrapper` in `agent/common.py` wrap every
tool result as:

```python
ToolReturn(return_value=safe_result, content=to_string(safe_result), metadata={})
```

There is **no size cap anywhere**. A `Read` of a 2 MB file, a `Bash` dumping
500 KB, or a `Grep` with thousands of hits goes straight into the context
window. `prompt/markdown/message_summarizer.md` exists but is used by the
*history* summarizer (an LLM round-trip in `summarizer/`), not for per-call
truncation.

## Design

Add a deterministic, content-only cap inside the two wrappers in
`agent/common.py`.

```python
# zrb/llm/agent/truncate.py
def truncate_tool_content(content: str, *, limit: int | None) -> tuple[str, bool]:
    """Return (possibly-truncated content, was_truncated).

    limit is the max number of characters in the model-facing string.
    None or <= 0 disables truncation (returns content unchanged)."""
```

Rules:

- Truncate **only the `content` string** (what the model reads). Leave
  `return_value` whole — typed/programmatic consumers and `safe_copy_result`
  behavior are unchanged.
- On truncation, keep the head and tail (most tool output is informative at
  both ends — e.g. a command's invocation echo and its final error), inserting a
  marker in the middle:

  ```
  …[truncated 480.0 KB / 6123 lines. Re-read a narrower slice: Read with
  offset/limit, a tighter Grep pattern, or pipe through head/tail in Bash.]…
  ```

- Set `metadata={"truncated": True, "original_chars": <n>}` so downstream
  inspection / tests can detect it.

### Where the limit comes from

A new config attribute on the LLM config mixin:

```
CFG.LLM_MAX_TOOL_RESULT_CHARS   # default e.g. 50_000 (matches opencode's ~50 KB)
```

`0` or negative disables truncation entirely. The default is high enough that
**typical** tool outputs are untouched — it only fires on the pathological
outputs that already degrade the model today.

### Integration points

`agent/common.py`:

- `create_safe_wrapper`: after computing `content = to_string(safe_result)`,
  pass it through `truncate_tool_content(...)`; merge the truncation flag into
  `metadata`. Skip when the original func already returned a `ToolReturn`
  (respect the tool's own framing — it may have truncated deliberately).
- `SafeToolsetWrapper.call_tool`: same treatment for toolset (MCP) results that
  are not already `ToolReturn`.

## Regression analysis

| Risk | Mitigation |
|------|------------|
| Truncating output a downstream tool consumes programmatically | Truncate `content` only; `return_value` left whole. |
| Any cap changes behavior | Default cap (50 KB) leaves typical output untouched; the cap only fires on outputs that already hurt. `0` disables it. |
| Tool already returned a `ToolReturn` (e.g. deliberately framed) | Pass those through untouched — respect the tool's own content. |
| Double-truncation vs Read's own offset/limit | The marker points the model at the tool's own narrowing args rather than a new fetch path. |
| Unicode boundary split | Truncate on character count (Python str slicing is codepoint-safe), not bytes. |

This is the lowest-risk change and is arguably a latent-bug fix.

## Tests (`test/llm/agent/test_truncate.py` + additions to common tests)

- Content below limit → returned unchanged, `truncated` absent/False.
- Content above limit → head+tail preserved, marker present, length ≤ limit
  (+ marker), `metadata["truncated"] is True`.
- `limit=0` / negative → never truncates.
- A function returning a `ToolReturn` directly → passed through, never
  re-truncated.
- `return_value` preserved whole even when `content` is truncated.
