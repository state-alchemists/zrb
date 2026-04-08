"""
Model Tiering Example

Demonstrates custom_model_names, model_getter, and model_renderer to implement
automatic model downgrading based on cumulative request count within a session.

Tier schedule:
    Requests 1–3  → zrb:model-pro       (highest quality)
    Requests 4–6  → zrb:model-flash     (balanced)
    Requests 7+   → zrb:model-flash-lite (most efficient)

All three tier names are mapped to CFG.LLM_MODEL by the renderer, so you only
need one real model configured. The tier names appear in the UI info bar and
autocomplete so the user can always see (and override) the active tier.

Usage:
    cd examples/model-tiering
    zrb llm chat
"""

from zrb.builtin.llm.chat import llm_chat
from zrb.config.config import CFG

# =============================================================================
# Tier name constants
# =============================================================================

MODEL_PRO = "zrb:model-pro"
MODEL_FLASH = "zrb:model-flash"
MODEL_FLASH_LITE = "zrb:model-flash-lite"

CUSTOM_MODEL_NAMES = [MODEL_PRO, MODEL_FLASH, MODEL_FLASH_LITE]

# =============================================================================
# Tier tracker — decides which tier to use per request
# =============================================================================


class ModelTierTracker:
    """Switches model tier based on cumulative LLM request count.

    Tier schedule (0-indexed count before increment):
        count 0–2  → zrb:model-pro
        count 3–5  → zrb:model-flash
        count 6+   → zrb:model-flash-lite
    """

    def __init__(self):
        self._count = 0

    def __call__(self, user_model):
        """Called by LLMTask before each LLM request.

        Args:
            user_model: The model specified by the user (ignored here — tier
                        is determined solely by request count).

        Returns:
            The tier name to use for this request.
        """
        tier = self._resolve_tier()
        self._count += 1
        return tier

    def _resolve_tier(self):
        if self._count < 3:
            return MODEL_PRO
        if self._count < 6:
            return MODEL_FLASH
        return MODEL_FLASH_LITE


# =============================================================================
# Model renderer — maps tier names to the real configured model
# =============================================================================

_CUSTOM_MODEL_SET = set(CUSTOM_MODEL_NAMES)


def render_model(model):
    """Translate a custom tier name into the actual model used for API calls.

    Any of the three tier names resolves to CFG.LLM_MODEL so you only need
    one API key / endpoint. Non-tier values (e.g., a fully-qualified model
    name typed via /model) are passed through unchanged.
    """
    if model in _CUSTOM_MODEL_SET:
        return CFG.LLM_MODEL
    return model


# =============================================================================
# Wire everything into llm_chat
# =============================================================================

tracker = ModelTierTracker()

llm_chat.custom_model_names = CUSTOM_MODEL_NAMES  # shown in /model autocomplete
llm_chat.model_getter = tracker                    # decides tier per request
llm_chat.model_renderer = render_model             # maps tier → real model
