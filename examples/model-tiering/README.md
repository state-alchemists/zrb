# Model Tiering Example

This example demonstrates `custom_model_names`, `model_getter`, and `model_renderer` to implement automatic model downgrading based on how many turns the chat has run.

## How It Works

Three features work together:

| Feature | Purpose |
|---|---|
| `custom_model_names` | Offers the tier names in `/model` autocomplete |
| `model_getter` | Called once per turn, when the agent is built — returns the active tier name |
| `model_renderer` | Translates a tier name into the real model sent to the API |

### Tier Schedule

```
Turns 1–3  → zrb:model-pro        (highest quality)
Turns 4–6  → zrb:model-flash      (balanced)
Turns 7+   → zrb:model-flash-lite  (most efficient)
```

All three tier names resolve to `CFG.LLM_MODEL` at runtime, so only one API key / endpoint is needed. A "turn" is one agent run: every model request inside it (including tool-call round-trips) uses the same tier. A `/btw` side question also builds an agent, so it advances the count too.

### Pipeline per Request

```
user model input
      │
      ▼
model_getter(user_model)   ← ignores user input, picks tier by count
      │ active tier name
      ▼
model_renderer(tier_name)  ← maps tier → CFG.LLM_MODEL
      │ real model         ← shown in UI info bar
      ▼
pydantic_ai Agent
```

## Quick Start

```bash
cd examples/model-tiering
zrb llm chat
```

Send a few messages. The info bar shows the *rendered* model, so with every tier mapped to `CFG.LLM_MODEL` it stays the same; map each tier to a different real model (see Customization) to watch it change.

## Code

```python
from zrb.builtin.llm.chat import llm_chat
from zrb.config.config import CFG

MODEL_PRO = "zrb:model-pro"
MODEL_FLASH = "zrb:model-flash"
MODEL_FLASH_LITE = "zrb:model-flash-lite"

CUSTOM_MODEL_NAMES = [MODEL_PRO, MODEL_FLASH, MODEL_FLASH_LITE]


class ModelTierTracker:
    def __init__(self):
        self._count = 0

    def __call__(self, user_model):
        tier = self._resolve_tier()
        self._count += 1
        return tier

    def _resolve_tier(self):
        if self._count < 3:
            return MODEL_PRO
        if self._count < 6:
            return MODEL_FLASH
        return MODEL_FLASH_LITE


def render_model(model):
    if model in set(CUSTOM_MODEL_NAMES):
        return CFG.LLM_MODEL
    return model


tracker = ModelTierTracker()

llm_chat.custom_model_names = CUSTOM_MODEL_NAMES
llm_chat.model_getter = tracker
llm_chat.model_renderer = render_model
```

## Customization

**Change tier thresholds** — edit `_resolve_tier()` in `ModelTierTracker`.

**Map tiers to different models** — update `render_model()` to return different model strings per tier instead of always using `CFG.LLM_MODEL`.

**Reset the counter per session** — hook into `SESSION_START` to reset `tracker._count = 0` (see `examples/llm-hooks/`).

**Honor `/model`** — this getter ignores `user_model`, so `/model` has no effect on the main agent while it is installed. Return `user_model` from the getter when you want an explicit choice to win; the renderer already passes non-tier names through unchanged.

## See Also

- `src/zrb/llm/config/model_resolver.py` — model-name resolution (the old `LLMConfig`
  singleton is removed in 3.x)
- `src/zrb/llm/task/llm_task.py` — `model_getter` / `model_renderer` (task-scoped properties)
- `src/zrb/llm/task/chat/task.py` — `custom_model_names` parameter on `LLMChatTask`
- `examples/llm-hooks/` — hook system for session lifecycle events
- `src/zrb/config/config.py` — `CFG.LLM_MODEL` and other defaults
