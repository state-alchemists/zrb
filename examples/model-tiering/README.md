# Model Tiering Example

This example demonstrates `custom_model_names`, `model_getter`, and `model_renderer` to implement automatic model downgrading based on cumulative request count.

## How It Works

Three features work together:

| Feature | Purpose |
|---|---|
| `custom_model_names` | Registers tier names for `/model` autocomplete and UI display |
| `model_getter` | Called before each LLM request — returns the active tier name |
| `model_renderer` | Translates a tier name into the real model sent to the API |

### Tier Schedule

```
Requests 1–3  → zrb:model-pro        (highest quality)
Requests 4–6  → zrb:model-flash      (balanced)
Requests 7+   → zrb:model-flash-lite  (most efficient)
```

All three tier names resolve to `CFG.LLM_MODEL` at runtime, so only one API key / endpoint is needed. The tier name is what appears in the UI info bar after each call.

### Pipeline per Request

```
user model input
      │
      ▼
model_getter(user_model)   ← ignores user input, picks tier by count
      │ active tier name   ← shown in UI info bar
      ▼
model_renderer(tier_name)  ← maps tier → CFG.LLM_MODEL
      │ real model
      ▼
pydantic_ai Agent
```

## Quick Start

```bash
cd examples/model-tiering
zrb llm chat
```

Send a few messages and watch the model name in the info bar cycle through the tiers.

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

**Override via `/model`** — the user can always type `/model zrb:model-pro` to force a specific tier, or any other model name to bypass tiering entirely (the renderer passes unknown names through unchanged).

## See Also

- `src/zrb/llm/task/llm_task.py` — `model_getter`, `model_renderer`, `custom_model_names`
- `src/zrb/llm/task/llm_chat_task.py` — same params on `LLMChatTask`
- `examples/llm-hooks/` — hook system for session lifecycle events
- `src/zrb/config/config.py` — `CFG.LLM_MODEL` and other defaults
