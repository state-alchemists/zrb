"""Composes the global `CFG` from category mixins.

The Config class is intentionally a thin shell — every property and DEFAULT_*
constant lives in a focused mixin under `_mixins/`. Public access stays flat:
`CFG.LLM_MODEL`, `CFG.WEB_HTTP_PORT`, `CFG.HOOKS_ENABLED`, etc. — nothing
external needs to change.

To find a setting:
- foundation/env/shell/init/version/banner   -> _mixins/foundation.py
- web HTTP/auth/branding/pagination          -> _mixins/web.py
- LLM model/API key/base URL                 -> _mixins/llm_core.py
- LLM UI styles/commands/intervals           -> _mixins/llm_ui.py
- LLM throttle/retry/timeout/size caps       -> _mixins/llm_limits.py
- LLM history/journal/snapshot/summarization -> _mixins/llm_content.py
- LLM prompt dirs/INCLUDE_* toggles          -> _mixins/llm_prompt.py
- LLM plugin/skill/agent search dirs         -> _mixins/llm_search.py
- RAG embedding/chunking                     -> _mixins/rag.py
- Internet search (SerpAPI/Brave/SearXNG)    -> _mixins/internet_search.py
- Hooks                                      -> _mixins/hooks.py
- Task runtime intervals/cmd buffer          -> _mixins/task_runtime.py
"""

from zrb.config._mixins.foundation import FoundationMixin
from zrb.config._mixins.hooks import HooksMixin
from zrb.config._mixins.internet_search import InternetSearchMixin
from zrb.config._mixins.llm_content import LLMContentMixin
from zrb.config._mixins.llm_core import LLMCoreMixin
from zrb.config._mixins.llm_limits import LLMLimitsMixin
from zrb.config._mixins.llm_prompt import LLMPromptMixin
from zrb.config._mixins.llm_search import LLMSearchMixin
from zrb.config._mixins.llm_ui import LLMUIMixin
from zrb.config._mixins.rag import RAGMixin
from zrb.config._mixins.task_runtime import TaskRuntimeMixin
from zrb.config._mixins.web import WebMixin


class Config(
    FoundationMixin,
    WebMixin,
    LLMCoreMixin,
    LLMUIMixin,
    LLMLimitsMixin,
    LLMContentMixin,
    LLMPromptMixin,
    LLMSearchMixin,
    RAGMixin,
    InternetSearchMixin,
    HooksMixin,
    TaskRuntimeMixin,
):
    """Global runtime configuration.

    Each mixin owns its DEFAULT_* constants and `@property` accessors. All
    cooperating `__init__` methods chain via `super().__init__()`, so creating
    a `Config()` populates every default in one pass.
    """


CFG = Config()
