You are currently on Zrb.
Zrb has two builtin LLM based tasks, `llm_ask` and `llm_chat`. Make sure you know in detail how things work.
You can start from `src/zrb/builtin/llm/llm_ask.py`.

`llm_ask` and `llm_chat` (and any `LLMTask` based task in general) has a default builtin system prompt that are crafted from several parts (see: `src/zrb/task/llm/prompt.py`).

Furthermore, `llm_ask` and `llm_chat` also carry tools documentation. All builtin tools are located at `src/zrb/builtin/llm/tool`.

You have two goals:
- Make system prompt components and tool description to be as brief and as clear as possible so that the LLM (even gemini-2.5-flash-lite) can works effectively.
- Adopt from `INSTRUCTION/gemini-prompt.md`. The gemini prompt is solely used for code assistant. Zrb on the otherhand should has a more general purpose. Any programming specific instruction should be located on the respected workflow (see: `src/zrb/task/llm/default_workflow`)

Improve zrb system prompt and tool description without fail.