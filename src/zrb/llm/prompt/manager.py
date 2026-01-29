from typing import TYPE_CHECKING, Callable

from zrb.context.any_context import AnyContext
from zrb.llm.prompt.prompt import SupportedRole
from zrb.util.attr import get_str_attr

if TYPE_CHECKING:
    from zrb.llm.note.manager import NoteManager
    from zrb.llm.skill.manager import SkillManager


PromptMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]


class PromptManager:
    def __init__(
        self,
        prompts: list[PromptMiddleware] | None = None,
        assistant_name: str | Callable[[AnyContext], str] | None = None,
        role: (
            str | SupportedRole | Callable[[AnyContext], str | SupportedRole] | None
        ) = None,
        include_persona: bool = True,
        include_mandate: bool = True,
        include_system_context: bool = True,
        include_note: bool = True,
        include_claude_compatibility: bool = True,
        include_zrb_prompt: bool = True,
        note_manager: "NoteManager | None" = None,
        skill_manager: "SkillManager | None" = None,
    ):
        self._middlewares = prompts or []
        self._assistant_name = assistant_name
        self._role = role
        self._include_persona = include_persona
        self._include_mandate = include_mandate
        self._include_system_context = include_system_context
        self._include_note = include_note
        self._include_claude_compatibility = include_claude_compatibility
        self._include_zrb_prompt = include_zrb_prompt
        self._note_manager = note_manager
        self._skill_manager = skill_manager
        self._composed_middlewares: list[PromptMiddleware] | None = None

    def _get_composed_middlewares(self, ctx: AnyContext) -> list[PromptMiddleware]:
        if self._composed_middlewares is not None:
            return self._composed_middlewares

        middlewares: list[PromptMiddleware] = []
        role = get_str_attr(ctx, self._role) if self._role else None
        assistant_name = (
            get_str_attr(ctx, self._assistant_name) if self._assistant_name else None
        )

        if self._include_persona:
            from zrb.llm.prompt.prompt import get_persona_prompt

            middlewares.append(
                new_prompt(
                    lambda: get_persona_prompt(assistant_name=assistant_name, role=role)
                )
            )
        if self._include_mandate:
            from zrb.llm.prompt.prompt import get_mandate_prompt

            middlewares.append(new_prompt(lambda: get_mandate_prompt(role=role)))
        if self._include_system_context:
            from zrb.llm.prompt.system_context import system_context

            middlewares.append(system_context)
        if self._include_note and self._note_manager:
            from zrb.llm.prompt.note import create_note_prompt

            middlewares.append(create_note_prompt(self._note_manager))
        if self._include_claude_compatibility and self._skill_manager:
            from zrb.llm.prompt.claude_compatibility import (
                create_claude_compatibility_prompt,
            )

            middlewares.append(create_claude_compatibility_prompt(self._skill_manager))
        if self._include_zrb_prompt:
            from zrb.llm.prompt.zrb import create_zrb_prompt

            middlewares.append(create_zrb_prompt())

        middlewares.extend(self._middlewares)
        self._composed_middlewares = middlewares
        return middlewares

    @property
    def prompts(self):
        return self._middlewares

    @prompts.setter
    def prompts(self, value: list[PromptMiddleware]):
        self._middlewares = value
        self._composed_middlewares = None

    def reset(self):
        self._middlewares = []
        self._composed_middlewares = None

    def add_prompt(self, *middleware: PromptMiddleware):
        self.append_middlewear(*middleware)

    def append_middlewear(self, *middleware: PromptMiddleware):
        self._middlewares.extend(middleware)
        self._composed_middlewares = None

    def compose_prompt(self) -> Callable[[AnyContext], str]:
        """
        Composes a list of prompt middlewares into a single prompt factory function.

        Each middleware should have the signature:
        (ctx: AnyContext, prompt: str, next: Callable[[AnyContext, str], str]) -> str

        The resulting function takes an AnyContext and returns the final prompt string.
        """

        def composed_prompt_factory(ctx: AnyContext) -> str:
            middlewares = self._get_composed_middlewares(ctx)

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
