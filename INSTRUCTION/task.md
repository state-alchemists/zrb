You are currently on Zrb.
Zrb has two builtin LLM based tasks, `llm_ask` and `llm_chat`. Make sure you know in detail how things work.
- `llm_ask` is non interactive
- `llm_chat` is interactive
You can start from `src/zrb/builtin/llm/llm_ask.py`. NOTE that llm_ask and llm_chat share a lot of system prompt components except the core system prompt itself.

`llm_ask` and `llm_chat` (and any `LLMTask` based task in general) has a default builtin system prompt that are crafted from several parts (see: `src/zrb/task/llm/prompt.py`).

Furthermore, `llm_ask` and `llm_chat` also carry tools documentation. All builtin tools are located at `src/zrb/builtin/llm/tool`. Additionally there is tool to load workflow at `src/zrb/task/llm/workflow.py`

You have two goals:
- Make system prompt components and tool description to be as brief and as clear as possible so that the LLM (even gemini-2.5-flash-lite) can works effectively.
  - Prioritize clarity over briefity. NEVER sacrifice clarity and quality for the sake of briefity
  - Make sure your update doesn't decrease LLM quality, make sure it still provide 
- Adopt from `INSTRUCTION/gemini-prompt.md`. The gemini prompt is solely used for code assistant. Zrb on the otherhand should has a more general purpose. Any programming specific instruction should be located on the respected workflow (see: `src/zrb/task/llm/default_workflow`). Improve all available workflows (not just coding). Make sure that zrb will produce quality at least as good as gemini cli (or even better).

Improve zrb system prompt and tool description without fail.