import inspect
from functools import partial
from typing import Any, Callable

from zrb.attr.type import StrListAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext, zrb_print
from zrb.llm.prompt.claude import (
    create_claude_skills_prompt,
    create_project_context_prompt,
)
from zrb.llm.prompt.live_context import render_live_context
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.prompt.system_context import system_context
from zrb.llm.prompt.tool_guidance import (
    ToolCatalogue,
    ToolGroups,
    get_tool_guidance_prompt,
)
from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager
from zrb.llm.util.git import is_inside_git_dir
from zrb.util.attr import get_str_attr, get_str_list_attr

# Simple prompt: just takes context and returns a string
SimplePrompt = Callable[[AnyContext], str | None]
# Full middleware: takes context, current prompt, and next handler
FullMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]
# Flexible middleware: can be either simple or full
PromptMiddleware = SimplePrompt | FullMiddleware


def _render_persona_prompt(assistant_name: str | None) -> str:
    """Render persona prompt with optional assistant name override."""
    effective = assistant_name if assistant_name is not None else CFG.LLM_ASSISTANT_NAME
    capitalized = effective[0].upper() + effective[1:] if effective else effective
    return get_prompt("persona", ASSISTANT_NAME=capitalized)


class PromptManager:
    """Assembles the LLM system prompt from ordered, MECE sections.

    Sections are emitted in the order given by ``include_sections`` (default in
    ``config/mixins/llm_prompt.py``: persona → mandate → git_mandate →
    journal_mandate → system_context → project_context → tool_guidance →
    claude_skills), followed by any user-added prompts. A section name that is
    not one of the built-ins resolves as a custom section: a provider registered
    via ``register_section`` (composed by calling it with the active context, for
    runtime-dynamic content) takes precedence, otherwise the content is loaded
    via ``get_prompt(name)`` (so ``"company_context"`` resolves
    ``company_context.md`` through the usual project-override → env →
    base-prompt-dir → package lookup). Either way downstreams add always-on,
    config-positioned sections without touching this class. ``tool_names`` and
    ``tool_guidance`` are resolved at runtime to
    filter per-tool guidance to the tools actually available; ``model`` and
    ``assistant_name`` may be callables resolved against the active context. See
    AGENTS.md ("LLM Prompt System").
    """

    def __init__(
        self,
        prompts: list[PromptMiddleware | str] | None = None,
        assistant_name: str | Callable[[AnyContext], str] | None = None,
        include_sections: list[str] | None = None,
        tool_names: "set[str] | Callable[[AnyContext], set[str]] | None" = None,
        tool_guidance: "ToolCatalogue | None" = None,
        tool_groups: "ToolGroups | None" = None,
        skill_manager: SkillManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        render: bool = False,
    ):
        self._middlewares = prompts or []
        self._assistant_name = assistant_name
        self._include_sections = include_sections  # None means "use CFG default"
        self._tool_names = tool_names
        self._tool_guidance: ToolCatalogue = (
            tool_guidance if tool_guidance is not None else {}
        )
        self._tool_groups: ToolGroups = tool_groups if tool_groups is not None else []
        self._skill_manager = skill_manager or default_skill_manager
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._render = render
        # Live context providers: per-turn dynamic state injected into the
        # <live-context> block after built-in rendering.
        self._live_context_providers: list[tuple[str, SimplePrompt]] = []
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
        # Pre-rendered Markdown blocks injected above the per-tool
        # catalogue when the ``tool_guidance`` section is composed. Set
        # by the task runner from model-aware section factories so the
        # blocks reflect the active model.
        self._tool_guidance_sections: list[str] = []

    @property
    def prompts(self):
        return self._middlewares

    @prompts.setter
    def prompts(self, value: list[PromptMiddleware | str]):
        self._middlewares = value

    @property
    def active_skills(self) -> StrListAttr | None:
        return self._active_skills

    @active_skills.setter
    def active_skills(self, value: StrListAttr | None):
        self._active_skills = value

    @property
    def include_sections(self) -> list[str] | None:
        return self._include_sections

    @include_sections.setter
    def include_sections(self, value: list[str] | None):
        self._include_sections = value

    @property
    def tool_names(self):
        return self._tool_names

    @tool_names.setter
    def tool_names(self, value: "set[str] | Callable[[AnyContext], set[str]] | None"):
        self._tool_names = value

    @property
    def model(self) -> Any:
        return self._model

    @model.setter
    def model(self, value: Any) -> None:
        self._model = value

    @property
    def tool_guidance_sections(self) -> list[str]:
        return self._tool_guidance_sections

    @tool_guidance_sections.setter
    def tool_guidance_sections(self, value: list[str] | None) -> None:
        self._tool_guidance_sections = list(value) if value else []

    def add_tool_group(self, *, name: str) -> None:
        """Register a new tool group if it does not already exist."""
        for label, _ in self._tool_groups:
            if label == name:
                return
        self._tool_groups.append((name, []))

    def add_tool_guidance(
        self,
        *,
        group: str,
        name: str,
        use_when: str | None = None,
        key_rule: str | None = None,
    ) -> None:
        """Add or update a tool entry within a group.

        If *group* does not yet exist it is created automatically.
        If *name* already exists in the catalogue its entry is
        overwritten, but its position inside the group is preserved.
        """
        # Ensure the group exists
        self.add_tool_group(name=group)

        # Update catalogue
        self._tool_guidance[name] = (use_when, key_rule)

        # Append to group members if not already there
        for label, members in self._tool_groups:
            if label == group:
                if name not in members:
                    members.append(name)
                break

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

    def add_live_context(self, name: str, provider: "SimplePrompt") -> None:
        """Register a dynamic per-turn live context provider.

        Called every turn inside ``create_live_context``, after built-in
        rendering. *provider* receives the active context and returns a string
        (or ``None`` / ``""`` to emit nothing). Re-registering the same *name*
        overwrites the previous provider.
        """
        for i, (existing_name, _) in enumerate(self._live_context_providers):
            if existing_name == name:
                self._live_context_providers[i] = (name, provider)
                return
        self._live_context_providers.append((name, provider))

    def reset(self):
        self._middlewares = []

    def add_prompt(self, *middleware: PromptMiddleware | str):
        self.append_prompt(*middleware)

    def append_prompt(self, *middleware: PromptMiddleware | str):
        self._middlewares.extend(middleware)

    def create_live_context(self, ctx: AnyContext) -> str:
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
        """
        body = render_live_context(ctx, self._model)
        for name, provider in self._live_context_providers:
            try:
                extra = provider(ctx)
                if extra:
                    body += "\n" + extra
            except Exception:
                pass
        if not body.strip():
            return ""
        return f"<live-context>\n{body}\n</live-context>"

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
                    # It's already a full middleware
                    middlewares.append(m)  # type: ignore
                else:
                    # It's a simple callable (ctx -> str), wrap it
                    middlewares.append(self._wrap_simple_prompt(m))  # type: ignore

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
        # Resolve sections: instance override or CFG default
        if self._include_sections is not None:
            sections = list(self._include_sections)
        else:
            sections = list(CFG.LLM_INCLUDE_SECTIONS)

        assistant_name = (
            get_str_attr(ctx, self._assistant_name) if self._assistant_name else None
        )
        tool_names_value = (
            self._tool_names(ctx) if callable(self._tool_names) else self._tool_names
        )

        # Capture values to avoid late-binding in lambdas
        _catalogue = self._tool_guidance
        _groups = self._tool_groups
        _skill_mgr = self._skill_manager

        middlewares: list[PromptMiddleware | str] = []

        for section in sections:
            if section == "persona":
                middlewares.append(
                    new_prompt(lambda an=assistant_name: _render_persona_prompt(an))
                )
            elif section == "git_mandate":
                middlewares.append(
                    new_prompt(
                        lambda: get_prompt("git_mandate") if is_inside_git_dir() else ""
                    )
                )
            elif section == "system_context":
                # Bind the resolved model so system_context can surface
                # capability-driven notes (e.g. "no parallel tool calls").
                middlewares.append(partial(system_context, model=self._model))
            elif section == "mandate":
                middlewares.append(new_prompt(lambda: get_prompt("mandate")))
            elif section == "tool_guidance":
                _extra_sections = list(self._tool_guidance_sections)
                middlewares.append(
                    new_prompt(
                        lambda tn=tool_names_value, c=_catalogue, g=_groups, es=_extra_sections: get_tool_guidance_prompt(
                            tn, c, g, extra_sections=es
                        )
                    )
                )
            elif section == "journal_mandate":
                middlewares.append(new_prompt(lambda: get_prompt("journal_mandate")))
            elif section == "project_context":
                middlewares.append(create_project_context_prompt())
            elif section == "claude_skills":
                if _skill_mgr:
                    active_skills = get_str_list_attr(
                        ctx, self._active_skills, self._render_active_skills
                    )
                    middlewares.append(
                        create_claude_skills_prompt(_skill_mgr, active_skills)
                    )
            elif section in self._section_providers:
                # Registered dynamic section -> composed by calling the
                # provider with the active context at compose time. Takes
                # precedence over a same-named markdown file. Registered via
                # register_section(); see AGENTS.md ("LLM Prompt System").
                middlewares.append(self._section_providers[section])
            else:
                # Unknown name -> file-backed custom section, resolved via
                # get_prompt(name) (project override -> env -> base prompt dir
                # -> package default). Lets downstreams add always-on, ordered
                # sections through include_sections + a markdown file, with no
                # code change. Missing files resolve to "" (harmless no-op)
                # and log a warning so a misspelled name is diagnosable.
                middlewares.append(self._new_file_section_middleware(section))

        # User custom prompts always last
        middlewares.extend(self._middlewares)
        return middlewares

    def _new_file_section_middleware(self, name: str) -> FullMiddleware:
        """Middleware for a file-backed custom section.

        Resolves *name* via ``get_prompt`` at compose time. When nothing
        resolves (no registered provider, no markdown file), the section is
        empty — a warning is logged so a misspelled name in
        ``include_sections`` / ``ZRB_LLM_INCLUDE_SECTIONS`` is diagnosable
        instead of silently dropped.
        """

        def file_section_middleware(
            ctx: AnyContext, current: str, next_fn: Callable[[AnyContext, str], str]
        ) -> str:
            content = get_prompt(name)
            if not content:
                message = (
                    f"Prompt section '{name}' is not a built-in, has no "
                    "registered provider, and no markdown file resolves for "
                    "it — the section is empty. Check include_sections / "
                    "ZRB_LLM_INCLUDE_SECTIONS for a typo."
                )
                log_warning = getattr(ctx, "log_warning", None)
                if callable(log_warning):
                    log_warning(message)
                else:
                    zrb_print(f"Warning: {message}", plain=True)
            return next_fn(ctx, f"{current}\n{content}")

        return file_section_middleware

    def _is_full_middleware(self, prompt: PromptMiddleware | str) -> bool:
        """Check if prompt is a full middleware (accepts next param) or simple callable."""
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
            # Get the prompt content
            if callable(prompt):
                content = prompt(ctx)
            else:
                content = prompt

            # Apply rendering if enabled (for string content)
            if self._render and isinstance(content, str):
                content = get_str_attr(ctx, content, auto_render=True)

            # Continue chain automatically
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
