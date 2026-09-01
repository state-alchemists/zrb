import inspect
from functools import partial
from typing import Any, Callable, TypeGuard, cast

from zrb.attr.type import StrListAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext, zrb_print
from zrb.llm.prompt.claude import (
    build_skill_replacements,
    create_project_context_prompt,
)
from zrb.llm.prompt.live_context import render_live_context, render_live_context_async
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

# Simple prompt: just takes context and returns a string
SimplePrompt = Callable[[AnyContext], str | None]
# Full middleware: takes context, current prompt, and next handler
FullMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]
# Flexible middleware: can be either simple or full
PromptMiddleware = SimplePrompt | FullMiddleware
# The five file-backed rule sections. `system_context` and `project_context`
# are composed separately: they are data sections built in Python, not files.
_SECTION_NAMES = frozenset({"persona", "principle", "workflow", "example", "profile"})


class _ProviderRegistry:
    """Named dynamic providers, composed in registration order.

    One shape used by live context: providers registered via
    ``add_live_context`` are called every turn and their non-empty output is
    appended to the block. A downstream provider that throws must never take
    the prompt down with it, so each is called under a try/except and skipped.
    """

    def __init__(self, label: str) -> None:
        self._label = label
        self._providers: list[tuple[str, SimplePrompt]] = []

    def set(self, name: str, provider: SimplePrompt) -> None:
        """Register *provider* under *name*, replacing any previous one."""
        for i, (existing, _) in enumerate(self._providers):
            if existing == name:
                self._providers[i] = (name, provider)
                return
        self._providers.append((name, provider))

    def render(self, ctx: AnyContext) -> list[str]:
        """Every provider's non-empty output, in registration order.

        A provider that raises is logged and skipped: these are downstream
        extension points, and one bad plugin must not cost the whole prompt.
        """
        parts: list[str] = []
        for name, provider in self._providers:
            try:
                extra = provider(ctx)
            except Exception as e:
                CFG.LOGGER.debug(f"{self._label} provider '{name}' failed: {e}")
                continue
            if extra:
                parts.append(extra)
        return parts


class PromptManager:
    """Assembles the LLM system prompt from ordered, MECE sections.

    Sections are emitted in the order given by ``include_sections`` (default in
    ``config/mixins/llm_prompt.py``: persona → principle → workflow → example →
    profile → system_context → project_context), followed by any user-added
    prompts. The first five are file-backed rule sections; the last two are
    runtime-fact sections built in Python — ``system_context`` renders the
    session-invariant environment (OS, CWD, tools, model), ``project_context``
    the project documentation discovered near the working directory. There is
    no prompt-side tool catalogue — what a tool does and which tool to reach
    for instead lives in the tool's own docstring, which pydantic-ai ships
    with the schema on every request.

    The skill catalogue is folded into the ``workflow`` section via
    ``{CORE_SKILLS}``/``{AVAILABLE_SKILLS}``/``{PREACTIVATED_SKILLS}``
    placeholders rather than a standalone section. A section name that is not one
    of the built-ins is ignored with a logged warning — a typo in a pinned
    config is visible rather than silently dropped. ``model`` and
    ``assistant_name`` may be callables resolved against the active context.
    See AGENTS.md ("LLM Prompt System").
    """

    def __init__(
        self,
        prompt_registry: PromptRegistry | None = None,
        prompts: PromptSetValue = None,
        assistant_name: str | Callable[[AnyContext], str] | None = None,
        include_sections: list[str] | None = None,
        skill_manager: SkillManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        render: bool = False,
    ):
        """Build a prompt manager.

        Every parameter is optional; `PromptManager()` composes the default
        section list against the shipped prompt files.

        Args:
            prompt_registry: Source of the default appended prompts when
                *prompts* is ``None``. Defaults to the global
                `prompt_registry`.
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
            render_active_skills: Whether to render `active_skills` entries as
                templates against the context.
            render: Whether string prompts in `prompts` are rendered as
                templates against the context.
        """
        self._prompt_registry = prompt_registry or default_prompt_registry
        self._middlewares: PromptSetValue = prompts
        # Ordered append/prepend/remove ops layered over the resolved base
        # (own value, else the registry's) at query time (ADR-0090).
        self._deltas = PromptDelta()
        self._assistant_name = assistant_name
        self._include_sections = include_sections  # None means "use CFG default"
        self._skill_manager = skill_manager or default_skill_manager
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._render = render
        # Live context providers: per-turn dynamic state injected into the
        # <live-context> block after built-in rendering.
        self._live_context_providers = _ProviderRegistry("Live-context")
        # Resolved current model — used by the system_context section to
        # surface model-specific capabilities (e.g. parallel tool call
        # support). Set by the task runner before each compose_prompt(),
        # so /model switches mid-session are reflected automatically.
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
        """Replace the appended prompts wholesale. ``None`` re-defers to the
        default registry. Clears all pending instance delta ops."""
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
        """The resolved prompt sections, in precedence order.

        Single source of truth for *which* sections are active:

        1. the instance ``include_sections`` override,
        2. ``CFG.LLM_INCLUDE_SECTIONS`` (an explicitly-set
           ``ZRB_LLM_INCLUDE_SECTIONS`` env var outranks
           ``DEFAULT_LLM_INCLUDE_SECTIONS`` inside the config).

        Journaling is not one of them: there is no prompt section to
        suppress, so ``LLM_JOURNAL_ENABLED`` gates the journal *tools* at
        registration instead (see ``apply_common_tools``), and the index
        injection checks the flag directly (``render_journal_index``).
        """
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
        """Drop every instance-appended prompt, returning to the default
        registry's prompt list."""
        self._middlewares = None
        self._deltas.clear()

    def _effective_prompts(self) -> PromptList:
        """The instance's resolved prompt list: its own explicit set (when
        set), or — when deferring — the default registry's *current* prompts,
        layered with this instance's ``append``/``prepend``/``remove`` ops."""
        if self._middlewares is None:
            base = self._prompt_registry.get_prompts()
        else:
            base = self._resolve_own_prompts(self._middlewares)
        return self._deltas.apply(base)

    def _resolve_own_prompts(self, value: PromptSetValue) -> PromptList:
        """Resolve this instance's own prompt value to a concrete list."""
        if callable(value):
            value = value()
        return [] if value is None else list(value)

    def append_prompt(self, *middleware: PromptMiddleware | str):
        """Append content emitted after all built-in sections.

        Accepts a static string, a `Callable[[AnyContext], str]`, or a full
        middleware `Callable[[ctx, current, next], str]`. The op is stored
        and layered over the resolved base each time the prompts are read,
        so a deferring manager keeps following its registry live.
        """
        self._deltas.append(*middleware)

    def prepend_prompt(self, *middleware: PromptMiddleware | str):
        """Prepend content run before the current instance prompts."""
        self._deltas.prepend(*middleware)

    def remove_prompt(self, middleware: PromptMiddleware | str) -> None:
        """Drop the first occurrence of the exact *middleware* from this
        instance's prompts, layered over the resolved base."""
        self._deltas.remove(middleware)

    def add_live_context(self, name: str, provider: SimplePrompt) -> None:
        """Register a dynamic per-turn live context provider.

        Called every turn inside ``create_live_context``, after built-in
        rendering. *provider* receives the active context and returns a string
        (or ``None`` / ``""`` to emit nothing). Re-registering the same *name*
        overwrites the previous provider.
        """
        self._live_context_providers.set(name, provider)

    def create_live_context(
        self,
        ctx: AnyContext,
        inject_journal_index: bool = False,
        first_message: str | None = None,
    ) -> str:
        """Render the per-turn volatile runtime state as a ``<live-context>``
        block for injection into the latest user message.

        Kept out of the system prompt on purpose: the block changes every turn
        (time, git, todos, …), so embedding it in the cached prefix would defeat
        prompt caching. Injecting it into the user turn instead keeps the system
        prompt byte-stable while still surfacing live state, and freezes a
        snapshot into history (older turns show what state *was*; the most
        recent block is authoritative — anchored in the system prompt). Returns
        ``""`` when there is nothing to report.

        Custom providers registered via ``add_live_context`` are called after
        the built-in rendering, in registration order.

        The journal index snapshot rides here rather than the cached system
        prompt. *inject_journal_index* picks the moment (first turn);
        ``render_journal_index`` itself checks ``LLM_JOURNAL_ENABLED``, so a
        disabled journal emits nothing regardless of what callers ask for.
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
        """``create_live_context`` for async callers (the per-turn hot path):
        the git subprocesses run off-loop instead of blocking the event loop.
        """
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
        """Build the ``system_context`` data section middleware.

        Renders the session-invariant system facts (OS, CWD, tools, model,
        sandbox, parallel-call support) via :func:`system_context`.
        """
        _builtin = partial(system_context, model=self._model)

        def system_context_middleware(
            ctx: AnyContext,
            current_prompt: str,
            next_handler: Callable[[AnyContext, str], str],
        ) -> str:
            return _builtin(ctx, current_prompt, next_handler)

        return system_context_middleware

    def _create_project_context_middleware(self) -> FullMiddleware:
        """Build the ``project_context`` data section middleware.

        Renders the project documentation files (AGENTS.md, CLAUDE.md, …)
        discovered near the working directory via ``create_project_context_prompt``.
        """
        _builtin = create_project_context_prompt()

        def project_context_middleware(
            ctx: AnyContext,
            current_prompt: str,
            next_handler: Callable[[AnyContext, str], str],
        ) -> str:
            return _builtin(ctx, current_prompt, next_handler)

        return project_context_middleware

    def compose_prompt(self) -> Callable[[AnyContext], str]:
        """
        Composes a list of prompt middlewares into a single prompt factory function.

        Supports both:
        - Simple prompts: Callable[[AnyContext], str] - just returns content
        - Full middlewares: Callable[[AnyContext, str, Callable], str] - controls chain
        - Strings: str - static content (with optional rendering)

        The resulting function takes an AnyContext and returns the final prompt string.
        """

        def composed_prompt_factory(ctx: AnyContext) -> str:
            raw_middlewares = self._get_composed_middlewares(ctx)

            # Normalize middlewares: strings and simple callables get wrapped
            middlewares: list[FullMiddleware] = []
            for m in raw_middlewares:
                if isinstance(m, str):
                    # Wrap string with rendering support
                    middlewares.append(self._wrap_simple_prompt(m))
                elif self._is_full_middleware(m):
                    # It's already a full middleware (narrowed by the TypeGuard)
                    middlewares.append(m)
                else:
                    # It's a simple callable (ctx -> str), wrap it. The branches
                    # above already ruled out str and the full-middleware shape.
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

        # The profile axis (ADR-0049): the `profile` section resolves
        # ``profile.{profile}.md`` with fallback to the base ``profile.md``;
        # the other sections are shared. ``active_profile`` resolves ``auto``
        # from the bound model.
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
        # Skill catalogue lives in workflow.md via {CORE_SKILLS}/{AVAILABLE_SKILLS}
        # /{PREACTIVATED_SKILLS} placeholders.
        if self._skill_manager:
            active_skills = get_str_list_attr(
                ctx, self._active_skills, self._render_active_skills
            )
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

        # User custom prompts always last
        middlewares.extend(self._effective_prompts())
        return middlewares

    def _file_section_middleware(
        self,
        name: str,
        profile: str | None = None,
        extra_replacements: dict[str, str] | None = None,
    ) -> FullMiddleware:
        """Middleware for one or more file-backed sections emitted as a unit.

        Resolves *name* via ``get_prompt`` at compose time,
        preferring the *profile* variant (``{name}.{profile}.md``) with fallback
        to the base file. When nothing resolves (no registered
        provider, no markdown file), the section is empty — a warning
        is logged so a misspelled name in ``include_sections`` /
        ``ZRB_LLM_INCLUDE_SECTIONS`` is diagnosable instead of silently dropped.

        *extra_replacements* are forwarded to ``get_prompt`` as
        ``**extra_replacements`` for ``{PLACEHOLDER}`` substitution.
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
        """Check if prompt is a full middleware (accepts next param) or simple callable.

        Typed as a `TypeGuard` so callers narrow on the positive branch instead
        of suppressing the resulting argument-type error.
        """
        if isinstance(prompt, str):
            return False
        if not callable(prompt):
            return False
        sig = inspect.signature(prompt)
        params = list(sig.parameters.values())
        # Full middleware has 3+ params: ctx, current_prompt, next, (optional *args, **kwargs)
        # Simple prompt has 1 param: ctx
        return len(params) >= 3

    def _wrap_simple_prompt(self, prompt: str | SimplePrompt) -> FullMiddleware:
        """Wrap a simple string or callable into a full middleware with rendering support."""

        def middleware(
            ctx: AnyContext, current: str, next_fn: Callable[[AnyContext, str], str]
        ) -> str:
            if callable(prompt):
                content = prompt(ctx)
            else:
                content = prompt

            if self._render and isinstance(content, str):
                content = get_str_attr(ctx, content, auto_render=True)

            new_prompt = f"{current}\n{content}" if content else current
            return next_fn(ctx, new_prompt)

        return middleware


def new_prompt(new_prompt: str | Callable[[], str], render: bool = False):
    def new_prompt_middleware(
        ctx: AnyContext, current_prompt: str, next: Callable[[AnyContext, str], str]
    ):
        effective_new_prompt = new_prompt() if callable(new_prompt) else new_prompt
        if render:
            effective_new_prompt = get_str_attr(
                ctx, effective_new_prompt, auto_render=True
            )
        return next(ctx, f"{current_prompt}\n{effective_new_prompt}")

    return new_prompt_middleware
