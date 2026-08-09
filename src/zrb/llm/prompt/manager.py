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
from zrb.llm.prompt.live_context import render_live_context
from zrb.llm.prompt.profile import Preset, active_preset
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.prompt.section_filter import filter_requires
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


class _ProviderRegistry:
    """Named dynamic providers, composed in registration order.

    One shape used three times: live context, system context, project context.
    Each had its own copy of "scan the list for this name, replace or append"
    and of "call each provider, swallow whatever it raises, keep the non-empty
    results" — the second of which is the part worth having once, since a
    downstream provider that throws must never take the prompt down with it.

    Not merged with ``_section_providers``: that one is a plain dict holding
    *one* provider per section, and composing it means picking a single entry
    rather than concatenating all of them.
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
    ``config/mixins/llm_prompt.py``: persona → workflow → examples →
    system_context → project_context), followed by any user-added prompts. Three
    of those carry rules; the last two carry runtime facts. There is no
    prompt-side tool catalogue — what a tool does and which tool to reach for
    instead lives in the tool's own docstring, which pydantic-ai ships with the
    schema on every request.

    The skill catalogue is folded into the ``workflow`` section via
    ``{CORE_SKILLS}``/``{AVAILABLE_SKILLS}``/``{PREACTIVATED_SKILLS}``
    placeholders rather than a standalone section. A section name that is not one
    of the built-ins resolves as a custom section: a provider registered via
    ``register_section`` (composed by calling it with the active context, for
    runtime-dynamic content) takes precedence, otherwise the content is loaded
    via ``get_prompt(name)`` (so ``"company_context"`` resolves
    ``company_context.md`` through the usual project-override → env →
    base-prompt-dir → package lookup). Either way downstreams add always-on,
    config-positioned sections without touching this class. A name that resolves
    to neither — including a retired section such as ``mandate`` or
    ``tool_guidance`` left in a pinned config — composes to nothing and logs a
    warning. ``model`` and ``assistant_name`` may be callables resolved against
    the active context. See AGENTS.md ("LLM Prompt System").
    """

    def __init__(
        self,
        prompts: list[PromptMiddleware | str] | None = None,
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
            prompts: Extra content emitted *after* every built-in section. Each
                entry is a string, a `Callable[[AnyContext], str]`, or a full
                middleware `Callable[[ctx, current, next], str]` that may
                rewrite the whole assembled prompt (detected by arity, 3+).
            assistant_name: Name substituted for `{ASSISTANT_NAME}`. A callable
                is resolved against the active context. Defaults to
                `CFG.LLM_ASSISTANT_NAME`.
            include_sections: Which sections compose, in order. `None` defers to
                the active preset, then to `CFG.LLM_INCLUDE_SECTIONS`.
            skill_manager: Source of the skill catalogue folded into `workflow`.
                Defaults to the global `skill_manager`.
            active_skills: Skills to pre-activate, listed in the prompt as
                already loaded.
            render_active_skills: Whether to render `active_skills` entries as
                templates against the context.
            render: Whether string prompts in `prompts` are rendered as
                templates against the context.
        """
        self._middlewares = prompts or []
        self._assistant_name = assistant_name
        self._include_sections = include_sections  # None means "use CFG default"
        self._skill_manager = skill_manager or default_skill_manager
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._render = render
        # Live context providers: per-turn dynamic state injected into the
        # <live-context> block after built-in rendering.
        self._live_context_providers = _ProviderRegistry("Live-context")
        # Project context providers: registered via add_project_context();
        # composed into the project_context section alongside the built-in
        # project documentation content.
        self._project_context_providers = _ProviderRegistry("Project-context")
        # System context providers: registered via add_system_context();
        # composed into the system_context section alongside the built-in
        # system context (OS, CWD, tools, etc.).
        self._system_context_providers = _ProviderRegistry("System-context")
        # Dynamic providers for config-positioned custom sections, keyed by the
        # name used in ``include_sections``. A registered provider is composed
        # by calling ``provider(ctx)`` at compose time; it takes precedence over
        # a same-named markdown file. See ``register_section``.
        self._section_providers: dict[str, SimplePrompt] = {}
        # Resolved current model — used by the system_context section to
        # surface model-specific capabilities (e.g. parallel tool call
        # support). Set by the task runner before each compose_prompt(),
        # so /model switches mid-session are reflected automatically.
        self._model: Any = None

    @property
    def prompts(self) -> list["PromptMiddleware | str"]:
        """The extra prompts appended after the built-in sections."""
        return self._middlewares

    @prompts.setter
    def prompts(self, value: list[PromptMiddleware | str]):
        """Replace the appended prompts wholesale."""
        self._middlewares = value

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
        """The explicit section override, or None to defer to preset/config.

        Read `active_sections` for the list actually in force.
        """
        return self._include_sections

    @include_sections.setter
    def include_sections(self, value: list[str] | None):
        """Pin the section list, overriding the preset and the config default."""
        self._include_sections = value

    @property
    def active_sections(self) -> list[str]:
        """The resolved prompt sections, in precedence order.

        Single source of truth for *which* sections are active:

        1. the instance ``include_sections`` override,
        2. an explicitly-set ``LLM_INCLUDE_SECTIONS`` env var,
        3. the active preset's section list, when it constrains that axis
           (only ``minimal`` does — ``full`` and ``lean`` reshape their prose
           through the variant axis and keep every section — ADR-0075),
        4. ``CFG.LLM_INCLUDE_SECTIONS``.

        Only the *env var* counts as the user naming a list: overriding
        ``CFG.DEFAULT_LLM_INCLUDE_SECTIONS`` in ``zrb_init.py`` changes the
        *default*, and a preset outranking a default is the intended precedence.

        Journaling is not one of them: there is no prompt section to
        suppress, so ``LLM_JOURNAL_ENABLED`` gates the journal *tools* at
        registration instead (see ``apply_common_tools``), and the index
        injection checks the flag directly (``render_journal_index``).
        """
        if self._include_sections is not None:
            return list(self._include_sections)
        sections = self.active_preset.sections
        if sections is not None and not CFG.is_env_set("LLM_INCLUDE_SECTIONS"):
            return list(sections)
        return list(CFG.LLM_INCLUDE_SECTIONS)

    @property
    def active_preset(self) -> Preset:
        """The preset the configured ``LLM_PROFILE`` binds for the active model.

        Read for two of its three axes: the section list above, and the phrasing
        variant threaded to file-backed sections in ``_get_composed_middlewares``.
        The third — the tool surface — is applied by ``apply_common_tools``.
        """
        return active_preset(self._model)

    @property
    def model(self) -> Any:
        """The model the prompt is being composed for; drives preset selection."""
        return self._model

    @model.setter
    def model(self, value: Any) -> None:
        """Bind the active model. Set by the runner before each compose."""
        self._model = value

    def register_section(self, name: str, provider: SimplePrompt) -> None:
        """Register a dynamic provider for a config-positioned custom section.

        Once registered, *name* may appear in ``include_sections`` (or the
        ``ZRB_LLM_INCLUDE_SECTIONS`` env var) and is composed at that position
        by calling ``provider(ctx)`` at compose time, so the content reflects
        live runtime state. *provider* must accept the active context and return
        a string (``Callable[[AnyContext], str]``); return ``""`` to emit
        nothing.

        Resolution precedence for a section name is built-in > registered
        provider > markdown file: a registered provider shadows a same-named
        ``get_prompt(name)`` file but never a built-in section. Re-registering
        the same name overwrites the previous provider.
        """
        self._section_providers[name] = provider

    def reset(self):
        """Drop every appended prompt, keeping the built-in sections."""
        self._middlewares = []

    def append_prompt(self, *middleware: PromptMiddleware | str):
        """Append content emitted after all built-in sections.

        Accepts a static string, a `Callable[[AnyContext], str]`, or a full
        middleware `Callable[[ctx, current, next], str]`.
        """
        self._middlewares.extend(middleware)

    def add_live_context(self, name: str, provider: SimplePrompt) -> None:
        """Register a dynamic per-turn live context provider.

        Called every turn inside ``create_live_context``, after built-in
        rendering. *provider* receives the active context and returns a string
        (or ``None`` / ``""`` to emit nothing). Re-registering the same *name*
        overwrites the previous provider.
        """
        self._live_context_providers.set(name, provider)

    def create_live_context(
        self, ctx: AnyContext, inject_journal_index: bool = False
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
        prompt (ADR-0042). *inject_journal_index* picks the moment (first turn);
        ``render_journal_index`` itself checks ``LLM_JOURNAL_ENABLED``, so a
        disabled journal emits nothing regardless of what callers ask for.
        """
        body = render_live_context(
            ctx, self._model, inject_journal_index=inject_journal_index
        )
        return self._finish_live_context(body, ctx)

    async def create_live_context_async(
        self, ctx: AnyContext, inject_journal_index: bool = False
    ) -> str:
        """``create_live_context`` for async callers (the per-turn hot path):
        the git subprocesses run off-loop instead of blocking the event loop.
        """
        # lazy: keep the async twin's import local, mirroring the sync path.
        from zrb.llm.prompt.live_context import render_live_context_async

        body = await render_live_context_async(
            ctx, self._model, inject_journal_index=inject_journal_index
        )
        return self._finish_live_context(body, ctx)

    def _finish_live_context(self, body: str, ctx: AnyContext) -> str:
        """Append registered live-context providers and wrap the block."""
        for extra in self._live_context_providers.render(ctx):
            body += "\n" + extra
        if not body.strip():
            return ""
        return f"<live-context>\n{body}\n</live-context>"

    def add_system_context(self, name: str, provider: SimplePrompt) -> None:
        """Register a dynamic system context provider.

        Called every turn inside the ``system_context`` section, after the
        built-in system context rendering (OS, CWD, tools, model, etc.).
        *provider* receives the active context and returns a string (or
        ``None`` / ``""`` to emit nothing). Re-registering the same *name*
        overwrites the previous provider.
        """
        self._system_context_providers.set(name, provider)

    def _create_system_context_middleware(self) -> FullMiddleware:
        """Build the system_context section middleware, including custom providers."""
        _builtin = partial(system_context, model=self._model)
        _providers = self._system_context_providers

        def system_context_middleware(
            ctx: AnyContext,
            current_prompt: str,
            next_handler: Callable[[AnyContext, str], str],
        ) -> str:
            result = _builtin(ctx, current_prompt, next_handler)
            extra_parts = _providers.render(ctx)
            if extra_parts:
                result = next_handler(
                    ctx,
                    f"{result}\n\n" + "\n\n".join(extra_parts),
                )
            return result

        return system_context_middleware

    def add_project_context(self, name: str, provider: SimplePrompt) -> None:
        """Register a dynamic project context provider.

        Called every turn inside the ``project_context`` section, after the
        built-in project documentation rendering. *provider* receives the
        active context and returns a string (or ``None`` / ``""`` to emit
        nothing). Re-registering the same *name* overwrites the previous
        provider.
        """
        self._project_context_providers.set(name, provider)

    def _create_project_context_middleware(self) -> FullMiddleware:
        """Build the project_context section middleware, including custom providers."""
        _builtin = create_project_context_prompt()
        _providers = self._project_context_providers

        def project_context_middleware(
            ctx: AnyContext,
            current_prompt: str,
            next_handler: Callable[[AnyContext, str], str],
        ) -> str:
            result = _builtin(ctx, current_prompt, next_handler)
            extra_parts = _providers.render(ctx)
            if extra_parts:
                result = next_handler(
                    ctx,
                    f"{result}\n\n## Custom Project Context\n"
                    + "\n\n".join(extra_parts),
                )
            return result

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

        # The preset's phrasing axis (ADR-0075): file-backed sections resolve
        # ``{name}.{variant}.md`` with fallback to the base (ADR-0047), which is
        # how ``lean`` and ``minimal`` get their lighter rulebooks. ``full``
        # carries no variant, so every section takes the base file.
        variant = self.active_preset.variant

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
        # Cross-reference blocks are filtered against the section set so the
        # prompt never points at a section it did not emit.
        emitted = set(sections)

        for section in sections:
            if section == "system_context":
                middlewares.append(self._create_system_context_middleware())
            elif section == "project_context":
                middlewares.append(self._create_project_context_middleware())
            elif section in self._section_providers:
                # Registered dynamic section -> composed by calling the
                # provider with the active context at compose time. Takes
                # precedence over a same-named markdown file. Registered via
                # register_section(); see AGENTS.md ("LLM Prompt System").
                middlewares.append(self._section_providers[section])
            else:
                # Built-in file-backed sections (persona, workflow, examples)
                # and unknown/custom ones both resolve here, via
                # get_prompt(name, **_extra) (project override -> env -> base
                # prompt dir -> package default). Lets downstreams add always-on,
                # ordered sections through include_sections + a markdown file,
                # with no code change. Missing files resolve to "" (harmless
                # no-op) and log a warning, which is also what a retired section
                # name left in a pinned config does.
                middlewares.append(
                    self._file_section_middleware(
                        section,
                        profile=variant,
                        extra_replacements=_extra,
                        emitted=emitted,
                    )
                )

        # User custom prompts always last
        middlewares.extend(self._middlewares)
        return middlewares

    def _file_section_middleware(
        self,
        name: str,
        profile: str | None = None,
        extra_replacements: dict[str, str] | None = None,
        emitted: set[str] | None = None,
    ) -> FullMiddleware:
        """Middleware for one or more file-backed sections emitted as a unit.

        Resolves *name* via ``get_prompt`` at compose time,
        preferring the *profile* variant (``{name}.{profile}.md``) with fallback
        to the base file (ADR-0047). When nothing resolves (no registered
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
            present = emitted if emitted is not None else {name}
            content = get_prompt(name, profile=profile, **kwargs)
            if not content:
                self._warn_empty_section(ctx, name)
            return next_fn(ctx, f"{current}\n" + filter_requires(content, present))

        return file_section_middleware

    def _warn_empty_section(self, ctx: AnyContext, name: str) -> None:
        """Surface a section name that resolved to nothing, so typos are visible."""
        message = (
            f"Prompt section '{name}' is not a built-in, has no "
            "registered provider, and no markdown file resolves for "
            "it — the section is empty. Check include_sections / "
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
