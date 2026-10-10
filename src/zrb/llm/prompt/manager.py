import inspect
from collections.abc import Callable
from functools import partial
from typing import Any, TypeGuard, cast

from zrb.attr.type import StrListAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext, zrb_print
from zrb.llm.prompt.claude import (
    build_skill_replacements,
    create_project_context_prompt,
)
from zrb.llm.prompt.live_context import render_live_context, render_live_context_async
from zrb.llm.prompt.live_context_providers import LiveContextProviders, SimplePrompt
from zrb.llm.prompt.profile import active_profile
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.prompt.registry import (
    PromptDelta,
    PromptList,
    PromptRegistry,
    PromptSetValue,
)
from zrb.llm.prompt.registry import prompt_registry as default_prompt_registry
from zrb.llm.prompt.system_context import system_context
from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager
from zrb.util.attr import get_str_attr, get_str_list_attr

# Full middleware: takes context, current prompt, and next handler
FullMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]
# Flexible middleware: can be either simple or full
PromptMiddleware = SimplePrompt | FullMiddleware
# The five file-backed rule sections. `system_context` and `project_context`
# are composed separately: they are data sections built in Python, not files.
_SECTION_NAMES = frozenset({"persona", "principle", "workflow", "example", "profile"})


class PromptManager:
    """Assembles the LLM system prompt from ordered sections.

    Sections follow ``include_sections`` (default in
    ``config/mixins/llm_prompt.py``), then any user-added prompts. Five are
    file-backed; ``system_context`` and ``project_context`` are built in Python.
    An unknown section name is ignored with a warning. See AGENTS.md
    ("LLM Prompt System").
    """

    def __init__(
        self,
        prompts: PromptSetValue = None,
        assistant_name: str | Callable[[AnyContext], str] | None = None,
        include_sections: list[str] | None = None,
        skill_manager: SkillManager | None = None,
        active_skills: StrListAttr | None = None,
        prompt_registry: PromptRegistry | None = None,
    ):
        """Build a prompt manager.

        Args:
            prompts: Extra content emitted *after* every built-in section.
                Each entry is a string, a `Callable[[AnyContext], str]`, or a
                full middleware
                `Callable[[ctx, current, next], str]` that may rewrite the
                whole assembled prompt (detected by arity, 3+). May instead
                be a zero-arg callable resolving to that list, evaluated at
                compose time. ``None`` defers to
                *prompt_registry*.
            assistant_name: Name substituted for `{ASSISTANT_NAME}`. A callable
                is resolved against the active context. Defaults to
                `CFG.LLM_ASSISTANT_NAME`.
            include_sections: Which sections compose, in order. `None` defers to
                `CFG.LLM_INCLUDE_SECTIONS`.
            skill_manager: Source of the skill catalogue folded into `workflow`.
                Defaults to the global `skill_manager`.
            active_skills: Skills to pre-activate, listed in the prompt as
                already loaded.
            prompt_registry: Source of default prompts when `prompts` is
                ``None``. Defaults to the global `prompt_registry`.
        """
        self._prompt_registry = prompt_registry or default_prompt_registry
        self._middlewares: PromptSetValue = prompts
        self._deltas = PromptDelta()
        self._assistant_name = assistant_name
        self._include_sections = include_sections  # None means "use CFG default"
        self._skill_manager = skill_manager or default_skill_manager
        self._active_skills = active_skills
        self._live_context_providers = LiveContextProviders()
        # Set by the runner before each compose_prompt(), so /model is reflected.
        self._model: Any = None

    @property
    def prompt_registry(self) -> PromptRegistry:
        """The registry this manager reads default prompts from."""
        return self._prompt_registry

    @property
    def prompts(self) -> PromptList:
        """The extra prompts appended after the built-in sections, resolved."""
        return self._effective_prompts()

    @prompts.setter
    def prompts(self, value: PromptSetValue):
        """Replace the appended prompts wholesale (``None`` defers to the registry)."""
        self._middlewares = value
        self._deltas.clear()

    @property
    def active_skills(self) -> StrListAttr | None:
        """Skills listed in the prompt as already loaded, or None."""
        return self._active_skills

    @active_skills.setter
    def active_skills(self, value: StrListAttr | None):
        """Set the pre-activated skill list."""
        self._active_skills = value

    @property
    def include_sections(self) -> list[str] | None:
        """The explicit section override, or None to defer to the config default.

        Read `active_sections` for the list actually in force.
        """
        return self._include_sections

    @include_sections.setter
    def include_sections(self, value: list[str] | None):
        """Pin the section list, overriding the config default."""
        self._include_sections = value

    @property
    def active_sections(self) -> list[str]:
        """The resolved sections: ``include_sections``, else ``CFG.LLM_INCLUDE_SECTIONS``."""
        if self._include_sections is not None:
            return list(self._include_sections)
        return list(CFG.LLM_INCLUDE_SECTIONS)

    @property
    def model(self) -> Any:
        """The model the prompt is being composed for; selects the `profile` section."""
        return self._model

    @model.setter
    def model(self, value: Any) -> None:
        """Bind the active model. Set by the runner before each compose."""
        self._model = value

    def reset(self):
        """Drop every instance-appended prompt, deferring to the registry again."""
        self._middlewares = None
        self._deltas.clear()

    def _effective_prompts(self) -> PromptList:
        """Own prompts (else the registry's current ones) with delta ops applied."""
        if self._middlewares is None:
            base = self._prompt_registry.get_prompts()
        else:
            base = self._resolve_own_prompts(self._middlewares)
        return self._deltas.apply(base)

    def _resolve_own_prompts(self, value: PromptSetValue) -> PromptList:
        if callable(value):
            value = value()
        return [] if value is None else list(value)

    def append_prompt(self, *middleware: PromptMiddleware | str):
        """Append content emitted after all built-in sections.

        Accepts a string, a `Callable[[AnyContext], str]`, or a full
        middleware `Callable[[ctx, current, next], str]`.
        """
        self._deltas.append(*middleware)

    def prepend_prompt(self, *middleware: PromptMiddleware | str):
        """Prepend content run before the current instance prompts."""
        self._deltas.prepend(*middleware)

    def remove_prompt(self, middleware: PromptMiddleware | str) -> None:
        """Drop the first occurrence of the exact *middleware*."""
        self._deltas.remove(middleware)

    def add_live_context(self, name: str, provider: SimplePrompt) -> None:
        """Register a per-turn live-context provider, replacing any under *name*.

        *provider* returns a string, or ``None``/``""`` to emit nothing.
        """
        self._live_context_providers.add_provider(name, provider)

    def remove_live_context(self, name: str) -> None:
        """Drop the live-context provider under *name*. No-op if absent."""
        self._live_context_providers.remove_provider(name)

    def set_live_contexts(self, providers: "list[tuple[str, SimplePrompt]]") -> None:
        """Replace the whole live-context provider list wholesale."""
        self._live_context_providers.set_providers(providers)

    def get_live_contexts(self) -> "list[tuple[str, SimplePrompt]]":
        """The `(name, provider)` pairs, in registration order."""
        return self._live_context_providers.get_providers()

    def create_live_context(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """Render per-turn state as a ``<live-context>`` block for the latest user message.

        Kept out of the system prompt so its cacheable prefix stays byte-stable.
        Registered providers follow the built-in rendering. Returns ``""`` when
        there is nothing to report.
        """
        body = render_live_context(
            ctx,
            self._model,
            inject_journal_index=inject_journal_index,
            first_message=first_message,
        )
        return self._finish_live_context(body, ctx)

    async def create_live_context_async(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """``create_live_context`` with git subprocesses run off the event loop."""
        body = await render_live_context_async(
            ctx,
            self._model,
            inject_journal_index=inject_journal_index,
            first_message=first_message,
        )
        return self._finish_live_context(body, ctx)

    def _finish_live_context(self, body: str, ctx: AnyContext) -> str:
        """Append registered live-context providers and wrap the block."""
        for extra in self._live_context_providers.render(ctx):
            body += "\n" + extra
        if not body.strip():
            return ""
        return f"<live-context>\n{body}\n</live-context>"

    def _create_system_context_middleware(self) -> FullMiddleware:
        """Build the ``system_context`` section middleware."""
        _builtin = partial(system_context, model=self._model)

        def system_context_middleware(
            ctx: AnyContext,
            current_prompt: str,
            next_handler: Callable[[AnyContext, str], str],
        ) -> str:
            return _builtin(ctx, current_prompt, next_handler)

        return system_context_middleware

    def _create_project_context_middleware(self) -> FullMiddleware:
        """Build the ``project_context`` section middleware."""
        _builtin = create_project_context_prompt()

        def project_context_middleware(
            ctx: AnyContext,
            current_prompt: str,
            next_handler: Callable[[AnyContext, str], str],
        ) -> str:
            return _builtin(ctx, current_prompt, next_handler)

        return project_context_middleware

    def compose_prompt(self) -> Callable[[AnyContext], str]:
        """Compose the sections and middlewares into one ``ctx -> prompt`` factory.

        Entries may be strings, ``Callable[[AnyContext], str]``, or full
        middlewares ``Callable[[AnyContext, str, Callable], str]``.
        """

        def composed_prompt_factory(ctx: AnyContext) -> str:
            raw_middlewares = self._get_composed_middlewares(ctx)

            middlewares: list[FullMiddleware] = []
            for m in raw_middlewares:
                if isinstance(m, str):
                    middlewares.append(self._wrap_simple_prompt(m))
                elif self._is_full_middleware(m):
                    middlewares.append(m)
                else:
                    middlewares.append(self._wrap_simple_prompt(cast(SimplePrompt, m)))

            def dispatch(index: int, current_prompt: str) -> str:
                if index >= len(middlewares):
                    return current_prompt

                middleware = middlewares[index]

                def next_handler(c: AnyContext, p: str) -> str:
                    return dispatch(index + 1, p)

                return middleware(ctx, current_prompt, next_handler)

            return dispatch(0, "")

        return composed_prompt_factory

    def _get_composed_middlewares(
        self, ctx: AnyContext
    ) -> list[PromptMiddleware | str]:
        sections = self.active_sections

        variant = active_profile(self._model)

        assistant_name = (
            get_str_attr(ctx, self._assistant_name) if self._assistant_name else None
        )
        effective = (
            assistant_name if assistant_name is not None else CFG.LLM_ASSISTANT_NAME
        )
        _extra: dict[str, str] = (
            {"ASSISTANT_NAME": effective[0].upper() + effective[1:]}
            if effective
            else {}
        )
        if self._skill_manager:
            active_skills = get_str_list_attr(ctx, self._active_skills)
            _extra.update(build_skill_replacements(self._skill_manager, active_skills))

        middlewares: list[PromptMiddleware | str] = []
        for section in sections:
            if section == "system_context":
                middlewares.append(self._create_system_context_middleware())
            elif section == "project_context":
                middlewares.append(self._create_project_context_middleware())
            elif section not in _SECTION_NAMES:
                self._warn_empty_section(ctx, section)
                continue
            else:
                middlewares.append(
                    self._file_section_middleware(
                        section,
                        profile=variant if section == "profile" else None,
                        extra_replacements=_extra,
                    )
                )

        middlewares.extend(self._effective_prompts())
        return middlewares

    def _file_section_middleware(
        self,
        name: str,
        profile: str | None = None,
        extra_replacements: dict[str, str] | None = None,
    ) -> FullMiddleware:
        """Middleware resolving *name* (preferring its *profile* variant) at compose time.

        Warns when nothing resolves, so a misspelled section is visible.
        """

        def file_section_middleware(
            ctx: AnyContext, current: str, next_fn: Callable[[AnyContext, str], str]
        ) -> str:
            kwargs = extra_replacements or {}
            content = get_prompt(name, profile=profile, **kwargs)
            if not content:
                self._warn_empty_section(ctx, name)
            return next_fn(ctx, f"{current}\n{content}")

        return file_section_middleware

    def _warn_empty_section(self, ctx: AnyContext, name: str) -> None:
        """Surface a section name that resolved to nothing, so typos are visible."""
        message = (
            f"Prompt section '{name}' is not a known section and is ignored. "
            "Known sections: persona, principle, workflow, example, profile, "
            "system_context, project_context. Check include_sections / "
            f"{CFG.ENV_PREFIX}_LLM_INCLUDE_SECTIONS for a typo."
        )
        log_warning = getattr(ctx, "log_warning", None)
        if callable(log_warning):
            log_warning(message)
        else:
            zrb_print(f"Warning: {message}", plain=True)

    def _is_full_middleware(
        self, prompt: PromptMiddleware | str
    ) -> TypeGuard[FullMiddleware]:
        """True when *prompt* is a full middleware (3+ params) rather than a simple callable."""
        if isinstance(prompt, str):
            return False
        if not callable(prompt):
            return False
        sig = inspect.signature(prompt)
        params = list(sig.parameters.values())
        return len(params) >= 3

    def _wrap_simple_prompt(self, prompt: str | SimplePrompt) -> FullMiddleware:
        """Wrap a simple string or callable into a full middleware."""

        def middleware(
            ctx: AnyContext, current: str, next_fn: Callable[[AnyContext, str], str]
        ) -> str:
            if callable(prompt):
                content = prompt(ctx)
            else:
                content = prompt

            new_prompt = f"{current}\n{content}" if content else current
            return next_fn(ctx, new_prompt)

        return middleware


def new_prompt(new_prompt: str | Callable[[], str]):
    def new_prompt_middleware(
        ctx: AnyContext, current_prompt: str, next: Callable[[AnyContext, str], str]
    ):
        effective_new_prompt = new_prompt() if callable(new_prompt) else new_prompt
        return next(ctx, f"{current_prompt}\n{effective_new_prompt}")

    return new_prompt_middleware
