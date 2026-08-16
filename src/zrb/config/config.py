"""Composes the global `CFG` from category mixins.

The Config class is intentionally a thin shell — every property and DEFAULT_*
constant lives in a focused mixin under `_mixins/`. Public access stays flat:
`CFG.LLM_MODEL`, `CFG.WEB_HTTP_PORT`, `CFG.HOOKS_ENABLED`, etc. — nothing
external needs to change.

To find a setting:
- foundation/env/shell/init/version/banner   -> mixins/foundation.py
- web HTTP/auth/branding/pagination          -> mixins/web.py
- LLM model/API key/base URL                 -> mixins/llm_core.py
- LLM UI styles/commands/intervals           -> mixins/llm_ui.py
- LLM throttle/retry/timeout/size caps       -> mixins/llm_limits.py
- LLM history/journal/snapshot/summarization -> mixins/llm_content.py
- LLM prompt dirs/INCLUDE_* toggles          -> mixins/llm_prompt.py
- LLM sandbox (FS gate, shell wrapper)       -> mixins/llm_sandbox.py
- LLM plugin/skill/agent search dirs         -> mixins/llm_search.py
- RAG embedding/chunking                     -> mixins/rag.py
- Internet search (SerpAPI/Brave/SearXNG)    -> mixins/internet_search.py
- Hooks                                      -> mixins/hooks.py
- Task runtime intervals/cmd buffer          -> mixins/task_runtime.py
- CLI semantic colors (warning/error/muted)  -> mixins/cli_style.py
- Theme selection (ZRB_THEME preset)         -> mixins/theme.py
"""

from zrb.config.env_field import EnvField
from zrb.config.mixins.cli_style import ConfigCLIStyle
from zrb.config.mixins.foundation import FoundationMixin
from zrb.config.mixins.hooks import HooksMixin
from zrb.config.mixins.internet_search import InternetSearchMixin
from zrb.config.mixins.llm_content import ConfigLLMContent
from zrb.config.mixins.llm_core import LLMCoreMixin
from zrb.config.mixins.llm_limits import LLMLimitsMixin
from zrb.config.mixins.llm_prompt import ConfigLLMPrompt
from zrb.config.mixins.llm_sandbox import LLMSandboxMixin
from zrb.config.mixins.llm_search import ConfigLLMSearch
from zrb.config.mixins.llm_ui import LLMUIMixin
from zrb.config.mixins.rag import RAGMixin
from zrb.config.mixins.task_runtime import TaskRuntimeMixin
from zrb.config.mixins.theme import ThemeMixin
from zrb.config.mixins.web import WebMixin


class Config(  # noqa: E501  # Sibling parts TYPE_CHECKING-declare ENV_PREFIX/ROOT_GROUP_* (FoundationMixin read-write properties) as attrs for self-access; pyright flags the property-vs-attr composition as an incompatible override (false positive — all expose the same str type).
    FoundationMixin,
    WebMixin,
    LLMCoreMixin,
    LLMUIMixin,
    LLMLimitsMixin,
    ConfigLLMContent,
    ConfigLLMPrompt,
    LLMSandboxMixin,
    ConfigLLMSearch,
    RAGMixin,
    InternetSearchMixin,
    HooksMixin,
    TaskRuntimeMixin,
    ThemeMixin,
    ConfigCLIStyle,
):
    """Global runtime configuration.

    Each mixin owns its DEFAULT_* constants and `@property` accessors. All
    cooperating `__init__` methods chain via `super().__init__()`, so creating
    a `Config()` populates every default in one pass.
    """

    def is_env_set(self, name: str) -> bool:
        """Whether the user set the environment variable behind `CFG.<name>`.

        A read never answers this: an unset field falls back to its default, so
        the value alone cannot say whether the user chose it. Callers that must
        distinguish "chosen" from "defaulted" — e.g. a caller that must keep a
        user-pinned `ZRB_LLM_INCLUDE_SECTIONS` separate from the shipped default
        order —
        ask here rather than reconstructing the env key themselves.

        Raises `AttributeError` for a name that is not an `EnvField` (hand-written
        properties such as `LOGGER` have no env var to be set).
        """
        field = getattr(type(self), name, None)
        if not isinstance(field, EnvField):
            raise AttributeError(f"{name} is not an environment-backed config field")
        return field.is_set(self.ENV_PREFIX)


CFG = Config()
