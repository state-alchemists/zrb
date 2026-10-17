🔖 [Documentation Home](../README.md) > [LLM](./) > Recipes

# LLM Recipes

The common changes to `zrb llm chat`, each in the fewest lines that work. Every snippet here runs in the test suite (`test/architecture/test_recipes_run.py`), so it is correct as written. For the concepts behind them, see [Extending the LLM](extending-the-llm.md) and [LLM Collections](../configuration/llm-collections.md).

Python snippets go in a `zrb_init.py` at your project root; zrb runs it at startup.

## Table of Contents

- [Use an OpenAI-compatible gateway](#use-an-openai-compatible-gateway)
- [Add a tool to `zrb llm chat`](#add-a-tool-to-zrb-llm-chat)
- [Replace the persona](#replace-the-persona)
- [Append an instruction to the system prompt](#append-an-instruction-to-the-system-prompt)
- [Add a skill](#add-a-skill)
- [Add a sub-agent](#add-a-sub-agent)
- [Build your own chat task with zrb's tools](#build-your-own-chat-task-with-zrbs-tools)
- [Hear and voice emotion](#hear-and-voice-emotion)
- [See what is configured](#see-what-is-configured)

---

## Use an OpenAI-compatible gateway

```bash
export ZRB_LLM_BASE_URL=https://gateway.example.com/v1
export ZRB_LLM_API_KEY=sk-...
export ZRB_LLM_MODEL=my-model     # a bare name routes through the base URL
```

Ollama, OpenRouter, vLLM and LiteLLM all work this way. Provider-prefixed names (`anthropic:claude-...`) and the rest are in [LLM Models](../configuration/llm-models.md).

## Add a tool to `zrb llm chat`

<!-- recipe: add-tool -->
```python
from zrb.builtin import llm_chat
from zrb.llm.permission import Capability, tag


def lookup_ticket(ticket_id: str) -> str:
    """Return a ticket's title and status."""
    return f"{ticket_id}: Login page times out (open)"


llm_chat.append_tool(tag(lookup_ticket, Capability.READ))
```

The type hints and docstring are the schema the model sees. Do not add a `ctx` parameter: the model would be asked to supply it. `tag` declares what the tool does, so permission rules and [Plan Mode](plan-mode.md) can treat it correctly; an untagged tool is `UNKNOWN`, which Plan Mode denies. To give the tool to sub-agents too, register it on `tool_registry` (from `zrb.llm.tool_registry`) instead, and not on both.

## Replace the persona

Write the new persona to `.zrb/llm/prompt/persona.md`:

<!-- recipe: persona -->
```markdown
You are Ops Buddy, the on-call assistant for the payments team. Answer briefly.
```

zrb uses that file instead of the built-in persona; the other sections stay. The same name works for `principle`, `workflow` and the rest listed in [LLM System Prompts](../configuration/llm-prompts.md#overridable-prompts). `ZRB_LLM_PROMPT_PERSONA` does the same from the environment.

## Append an instruction to the system prompt

<!-- recipe: append-prompt -->
```python
from zrb.llm.prompt.registry import prompt_registry

prompt_registry.append_prompt(
    "Our services run on Kubernetes, so prefer kubectl over ssh, and never restart prod."
)
```

`ZRB_LLM_PROMPT` appends from the environment, but splits its value on commas into separate entries, so use `prompt_registry` for prose.

## Add a skill

Create `.zrb/skills/release-notes/SKILL.md`:

<!-- recipe: skill -->
```markdown
---
name: release-notes
description: Draft release notes from the git log since the last tag.
---
Run `git describe --tags --abbrev=0`, then `git log <tag>..HEAD --oneline`.
Group the commits into Features, Fixes and Other, one line each.
```

The model sees the name and description and loads the body when it needs it. `/release-notes` invokes it directly. See [Claude Compatibility](claude-compatibility.md) for the other locations and frontmatter keys.

## Add a sub-agent

Create `.zrb/agents/sql-reviewer.agent.md`:

<!-- recipe: agent -->
```markdown
---
name: sql-reviewer
description: Read-only. Reviews SQL migrations for locking and data-loss risks.
tools: [Read, Grep, Glob]
---
You review SQL migrations. List each risk with the line it comes from.
```

The main agent delegates to it through `DelegateToAgent`.

## Build your own chat task with zrb's tools

`LLMChatTask` on its own starts bare: no tools, no inputs. `apply_common_tools` gives it the same tools `zrb llm chat` has:

<!-- recipe: own-chat -->
```python
from zrb import LLMChatTask, StrInput, cli
from zrb.llm.common_tools import apply_common_tools

ops_chat = LLMChatTask(
    name="ops-chat",
    input=StrInput("message", "Message", allow_empty=True, always_prompt=False),
    message=lambda ctx: ctx.input.message,
)
apply_common_tools(ops_chat)
cli.add_task(ops_chat)
```

`zrb ops-chat --message "what is failing?"` then runs it. Adding a tool to `zrb llm chat` itself, as above, is usually all you need.

## Hear and voice emotion

The model opens each reply with an emoji for how it feels, which zrb takes out of the reply and reads it in that emotion's voice, and emotion2vec+ hears the tone of what you say. Install the local models first:

```bash
pip install "zrb[voice]" "pipecat-ai[pocket-tts,funasr]" torch sherpa-onnx huggingface_hub
```

Then, in `zrb_init.py`:

<!-- recipe: emotion -->
```python
import os

from zrb import CFG

CFG.LLM_VOICE = "conversation"  # speech, and hands-free dictation
CFG.LLM_EMOTION_ENABLED = True  # the reply's emoji, and the Emotion hook
CFG.LLM_DICTATION_DETECT_EMOTION = True  # your tone, heard by emotion2vec+
CFG.LLM_DICTATION_BACKEND = "sensevoice"
CFG.LLM_SPEECH_BACKEND = "pocket"
CFG.LLM_SPEECH_EMOTION_VOICES = {
    emotion: os.path.expanduser(f"~/voices/{emotion}.wav")
    for emotion in ("happy", "sad", "angry", "surprised", "relaxed", "neutral")
}
```

Each `.wav` is a short clip spoken in that emotion, which `pocket` clones, tone included; an emotion with no voice is read in `ZRB_LLM_SPEECH_VOICE`. Your tone reaches the model in its live context (`sounding sad (0.82)`), never in your words. emotion2vec+ and `pocket` run on PyTorch, which loads in the chat process, so Ctrl+C can be slow while it does. Each setting is in [LLM configuration § Emotion](../configuration/llm-voice-camera.md#emotion), and an avatar can follow both emotions through the [`Emotion` hook](hooks.md#emotion).

## See what is configured

```bash
zrb config explain               # every setting, its value, and whether it was set or defaulted
zrb config explain llm_model     # one setting in full, with its default
```
