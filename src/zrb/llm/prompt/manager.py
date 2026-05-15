import inspect
from typing import Callable

from zrb.attr.type import StrListAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.prompt.claude import (
    create_claude_skills_prompt,
    create_project_context_prompt,
)
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
SimplePrompt = Callable[[AnyContext], str]
# Full middleware: takes context, current prompt, and next handler
FullMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]
# Flexible middleware: can be either simple or full
PromptMiddleware = SimplePrompt | FullMiddleware


def _render_persona_prompt(assistant_name: str | None) -> str:
    """Render persona prompt with optional assistant name override."""
    effective = assistant_name if assistant_name else CFG.LLM_ASSISTANT_NAME
    capitalized = effective[0].upper() + effective[1:] if effective else effective
    return get_prompt("persona", ASSISTANT_NAME=capitalized)


class PromptManager:
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

    def reset(self):
        self._middlewares = []

    def add_prompt(self, *middleware: PromptMiddleware | str):
        self.append_prompt(*middleware)

    def append_prompt(self, *middleware: PromptMiddleware | str):
        self._middlewares.extend(middleware)

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
                middlewares.append(system_context)
            elif section == "mandate":
                middlewares.append(new_prompt(lambda: get_prompt("mandate")))
            elif section == "tool_guidance":
                middlewares.append(
                    new_prompt(
                        lambda tn=tool_names_value, c=_catalogue, g=_groups: get_tool_guidance_prompt(
                            tn, c, g
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

        # User custom prompts always last
        middlewares.extend(self._middlewares)
        return middlewares

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
