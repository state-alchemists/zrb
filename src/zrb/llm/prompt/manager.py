import inspect
from typing import Callable, Union

from zrb.attr.type import StrListAttr
from zrb.context.any_context import AnyContext
from zrb.llm.note.manager import NoteManager
from zrb.llm.prompt.claude import (
    create_claude_skills_prompt,
    create_project_context_prompt,
)
from zrb.llm.prompt.cli import create_cli_skills_prompt
from zrb.llm.prompt.note import create_note_prompt
from zrb.llm.prompt.prompt import get_mandate_prompt, get_persona_prompt
from zrb.llm.prompt.system_context import system_context
from zrb.llm.skill.manager import SkillManager
from zrb.util.attr import get_str_attr, get_str_list_attr

# Simple prompt: just takes context and returns a string
SimplePrompt = Callable[[AnyContext], str]
# Full middleware: takes context, current prompt, and next handler
FullMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]
# Flexible middleware: can be either simple or full
PromptMiddleware = Union[SimplePrompt, FullMiddleware]


class PromptManager:
    def __init__(
        self,
        prompts: list[PromptMiddleware | str] | None = None,
        assistant_name: str | Callable[[AnyContext], str] | None = None,
        include_persona: bool = True,
        include_mandate: bool = True,
        include_system_context: bool = True,
        include_note: bool = True,
        include_claude_skills: bool = True,
        include_cli_skills: bool = True,
        include_project_context: bool = True,
        note_manager: NoteManager | None = None,
        skill_manager: SkillManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        render: bool = False,
    ):
        self._middlewares = prompts or []
        self._assistant_name = assistant_name
        self._include_persona = include_persona
        self._include_mandate = include_mandate
        self._include_system_context = include_system_context
        self._include_note = include_note
        self._include_claude_skills = include_claude_skills
        self._include_cli_skills = include_cli_skills
        self._include_project_context = include_project_context
        self._note_manager = note_manager
        self._skill_manager = skill_manager
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._render = render

    def _get_composed_middlewares(
        self, ctx: AnyContext
    ) -> list[PromptMiddleware | str]:
        middlewares: list[PromptMiddleware | str] = []
        assistant_name = (
            get_str_attr(ctx, self._assistant_name) if self._assistant_name else None
        )
        if self._include_persona:
            middlewares.append(
                new_prompt(lambda: get_persona_prompt(assistant_name=assistant_name))
            )
        if self._include_mandate:
            middlewares.append(new_prompt(lambda: get_mandate_prompt()))
        if self._include_system_context:
            middlewares.append(system_context)
        if self._include_note and self._note_manager:
            middlewares.append(create_note_prompt(self._note_manager))
        if self._include_project_context:
            middlewares.append(create_project_context_prompt())
        if self._include_claude_skills and self._skill_manager:
            active_skills = get_str_list_attr(
                ctx, self._active_skills, self._render_active_skills
            )
            middlewares.append(
                create_claude_skills_prompt(self._skill_manager, active_skills)
            )
        if self._include_cli_skills:
            middlewares.append(create_cli_skills_prompt())
        middlewares.extend(self._middlewares)
        return middlewares

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
    def include_project_context(self):
        return self._include_project_context

    @include_project_context.setter
    def include_project_context(self, value: bool):
        self._include_project_context = value

    def reset(self):
        self._middlewares = []

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
