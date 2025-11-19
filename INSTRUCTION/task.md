# ANALYZE

You are currently on Zrb.
Zrb has two builtin LLM based tasks, `llm_ask` and `llm_chat`. 
- `llm_ask` is non interactive
- `llm_chat` is interactive
You can start from `src/zrb/builtin/llm/llm_ask.py`. NOTE that llm_ask and llm_chat share a lot of system prompt components except the core system prompt itself.

`llm_ask` and `llm_chat` (and any `LLMTask` based task in general) has a default builtin system prompt that are crafted from several parts (see: `src/zrb/task/llm/prompt.py`).

Furthermore, `llm_ask` and `llm_chat` also carry tools documentation. All builtin tools are located at `src/zrb/builtin/llm/tool`. Additionally there is tool to load workflow at `src/zrb/task/llm/workflow.py`

**IMPORTANT** Make sure you know in detail how things work internally by reading the code and implementation.

# GOAL

You have two goals:
- Make system prompt components and tool description to be as brief and as clear as possible so that Zrb can works better.
  - Prioritize clarity over briefity. NEVER sacrifice clarity and quality for the sake of briefity
  - Make sure your update doesn't decrease LLM quality, make sure it still provide necessary informations so that Zrb can use the tools wisely, effectively, and efficiently.
- Adopt from `INSTRUCTION/gemini-prompt.md` **BUT** consider that the gemini prompt is solely used for code assistant, while Zrb is more general purpose.
  - Adapt generic instruction into `src/zrb/config/default_prompt/interactive_system_prompt.md` and `src/zrb/config/default_prompt/system_prompt.md`
  - Adapt coding specific workflows into `src/zrb/task/llm/default_workflow`
