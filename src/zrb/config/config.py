"""Composes the global `CFG` from category mixins.

The Config class is intentionally a thin shell — every property and DEFAULT_*
constant lives in a focused mixin under `_mixins/`. Public access stays flat:
`CFG.LLM_MODEL`, `CFG.WEB_HTTP_PORT`, `CFG.HOOKS_ENABLED`, etc. — nothing
external needs to change.

To find a setting:
- foundation/env/shell/init/version/banner   -> mixins/foundation.py
- web HTTP/auth/branding/pagination          -> mixins/web.py
- LLM model/API key/base URL                 -> mixins/llm_core.py
- LLM UI styles/commands/intervals          -> mixins/llm_ui.py, which
  itself stitches together (not imported here directly) llm_ui_styles.py,
  llm_ui_commands.py and llm_ui_runtime.py
- Camera / dictation / speech / voice preset -> mixins/llm_camera.py,
  llm_dictation.py, llm_speech.py, llm_voice.py
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

import os
from typing import Any

from zrb.config.env_field import EnvField
from zrb.config.mixins.cli_style import CLIStyleMixin
from zrb.config.mixins.foundation import FoundationMixin
from zrb.config.mixins.hooks import HooksMixin
from zrb.config.mixins.internet_search import InternetSearchMixin
from zrb.config.mixins.llm_camera import LLMCameraMixin
from zrb.config.mixins.llm_content import LLMContentMixin
from zrb.config.mixins.llm_core import LLMCoreMixin
from zrb.config.mixins.llm_dictation import LLMDictationMixin
from zrb.config.mixins.llm_limits import LLMLimitsMixin
from zrb.config.mixins.llm_prompt import LLMPromptMixin
from zrb.config.mixins.llm_sandbox import LLMSandboxMixin
from zrb.config.mixins.llm_search import LLMSearchMixin
from zrb.config.mixins.llm_speech import LLMSpeechMixin
from zrb.config.mixins.llm_tools import LLMToolsMixin
from zrb.config.mixins.llm_ui import LLMUIMixin
from zrb.config.mixins.llm_voice import LLMVoiceMixin
from zrb.config.mixins.rag import RAGMixin
from zrb.config.mixins.task_runtime import TaskRuntimeMixin
from zrb.config.mixins.theme import ThemeMixin
from zrb.config.mixins.web import WebMixin
from zrb.config.retired import RETIRED_SETTINGS
from zrb.util.string.suggestion import suggest_name

# How alike a set variable must be to a setting's name to be called a typo of
# it: `BARGEIN` for `BARGE_IN` scores 0.99, `MAX_TOKEN_PER_MINUTE` for
# `LLM_MAX_TOKEN_PER_MINUTE` 0.92, while a project's own `ZRB_USE_BORG_*`
# scores 0.6 against its nearest setting.
_TYPO_CUTOFF = 0.85


def _is_assignable_field(cls: type, name: str) -> bool:
    """Whether ``name`` on ``cls`` has a path for ``CFG.<name> = ...``."""
    attr = getattr(cls, name, None)
    if isinstance(attr, EnvField):
        return True
    # A read-write @property; a read-only one (e.g. LOGGER) has no setter.
    return isinstance(attr, property) and attr.fset is not None


def _uncastable_setting_message(
    name: str, raw: str, field: EnvField, error: Exception
) -> str:
    accepted = (
        "'on' or 'off'" if field.is_boolean else f"a value parseable by {field.cast_name}()"
    )
    return f"CFG.{name} = {raw!r} is not valid: expected {accepted}. ({error})"


class Config(
    FoundationMixin,
    WebMixin,
    LLMCoreMixin,
    LLMUIMixin,
    LLMCameraMixin,
    LLMDictationMixin,
    LLMSpeechMixin,
    LLMVoiceMixin,
    LLMLimitsMixin,
    LLMContentMixin,
    LLMPromptMixin,
    LLMSandboxMixin,
    LLMSearchMixin,
    LLMToolsMixin,
    RAGMixin,
    InternetSearchMixin,
    HooksMixin,
    TaskRuntimeMixin,
    ThemeMixin,
    CLIStyleMixin,
):
    """Global runtime configuration.

    Each mixin owns its DEFAULT_* constants and `@property` accessors. All
    cooperating `__init__` methods chain via `super().__init__()`, so creating
    a `Config()` populates every default in one pass.

    Note: sibling parts `TYPE_CHECKING`-declare `ENV_PREFIX`/`ROOT_GROUP_*`
    (`FoundationMixin`'s read-write properties) as plain attributes for
    self-access; pyright flags the property-vs-attribute composition as an
    incompatible override on this class. False positive — every mixin
    exposes the same `str` type — so the class declaration is exempted
    from line-length linting rather than reworded to hide it.
    """

    def __setattr__(self, name: str, value: Any) -> None:
        """Reject an assignment to an UPPERCASE name this config does not define.

        `zrb_init.py` is configured by assignment, so a typo (`CFG.LLM_MODELL`)
        would otherwise be a silent no-op the user only notices as "my setting
        did not apply". Names that are not all-uppercase (internal `_state`) are
        left alone. `DEFAULT_*` names are exempt too: each mixin's `__init__`
        sets its own as a fresh instance attribute (not a class attribute), so
        checking them here would reject the very assignment that defines them.
        """
        if (
            name.isupper()
            and not name.startswith("DEFAULT_")
            and not hasattr(type(self), name)
        ):
            raise AttributeError(self._unknown_knob_message(name))
        super().__setattr__(name, value)

    def _unknown_knob_message(self, name: str) -> str:
        known = self.get_settable_field_names()
        suggestions = suggest_name(name, known)
        message = f"CFG has no setting named {name!r}."
        if suggestions:
            message += " Did you mean " + " / ".join(suggestions) + "?"
        return (
            message
            + f" ({len(known)} settings; see `{self.ROOT_GROUP_NAME} config explain`.)"
        )

    def get_settable_field_names(self) -> list[str]:
        """Sorted names of every setting assignable via ``CFG.<name> = ...``.

        The single enumeration of what counts as settable, shared by the
        unknown-knob suggestion and the `/set` slash command, so the two
        cannot drift on which fields a user may set.
        """
        return sorted(
            n
            for n in dir(type(self))
            if n.isupper()
            and not n.startswith("DEFAULT_")
            and _is_assignable_field(type(self), n)
        )

    def get_settable_field(self, name: str) -> "EnvField | None":
        """The `EnvField` descriptor behind settable field `name`, or None.

        Returns None when `name` is not a settable UPPERCASE `EnvField` — it
        may still be unknown, or a read-write `@property` (which has no cast).
        """
        if not name.isupper() or name.startswith("DEFAULT_"):
            return None
        attr = getattr(type(self), name, None)
        return attr if isinstance(attr, EnvField) else None

    def convert_setting_value(self, name: str, raw: str) -> object:
        """Convert `raw` to the value type of settable field `name`.

        Raises `AttributeError` (with the closest-real-knob suggestion) when
        `name` is not settable, and `ValueError` naming the setting, the bad
        value and the accepted values when `raw` cannot be cast to the
        field's type. Conversion follows a read, `transform` included, so the
        result is the effective value rather than the bare cast. A read-write
        `@property` has no cast, so its string is passed through unchanged.
        """
        if not _is_assignable_field(type(self), name):
            raise AttributeError(self._unknown_knob_message(name))
        field = getattr(type(self), name, None)
        if not isinstance(field, EnvField):
            return raw
        try:
            return field.convert(raw, self)
        except (ValueError, TypeError) as error:
            raise ValueError(
                _uncastable_setting_message(name, raw, field, error)
            ) from error

    def get_mistyped_env_keys(self) -> dict[str, str]:
        """Each set `<ENV_PREFIX>_*` variable no setting reads, mapped to the
        setting it most likely meant.

        A mistyped variable (`ZRB_LLM_MODELL`) is otherwise ignored without a
        word. Only a close match is reported, because the prefix is shared:
        a project's own `ZRB_DEPLOY_TARGET` read by its `zrb_init.py` is not
        a typo and must stay quiet.
        """
        known = sorted(
            key
            for name in dir(type(self))
            if isinstance(field := getattr(type(self), name, None), EnvField)
            for key in field.get_read_keys(self.ENV_PREFIX)
        )
        skipped = set(known) | set(self.get_retired_env_keys())
        mistyped: dict[str, str] = {}
        for key in sorted(os.environ):
            if not key.startswith(f"{self.ENV_PREFIX}_") or key in skipped:
                continue
            matches = suggest_name(key, known, limit=1, cutoff=_TYPO_CUTOFF)
            if matches:
                mistyped[key] = matches[0]
        return mistyped

    def get_retired_env_keys(self) -> dict[str, str]:
        """Each set variable of a setting zrb no longer reads, mapped to what
        to set instead (or why there is nothing to set)."""
        retired: dict[str, str] = {}
        for name, instead in RETIRED_SETTINGS.items():
            key = f"{self.ENV_PREFIX}_{name}"
            if key in os.environ:
                is_setting = instead.isupper() and " " not in instead
                retired[key] = f"{self.ENV_PREFIX}_{instead}" if is_setting else instead
        return retired

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
