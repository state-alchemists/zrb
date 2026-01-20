from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.util.attr import get_str_attr

PromptMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]


class PromptManager:
    def __init__(self, middlewares: list[PromptMiddleware] = []):
        self._middlewares = middlewares

    @property
    def middleware(self):
        return self._middlewares

    @middleware.setter
    def middleware(self, value: list[PromptMiddleware]):
        self._middlewares = value

    def add_middleware(self, *middleware: PromptMiddleware):
        self.append_middlewear(*middleware)

    def append_middlewear(self, *middleware: PromptMiddleware):
        self._middlewares += middleware

    def compose_prompt(self) -> Callable[[AnyContext], str]:
        """
        Composes a list of prompt middlewares into a single prompt factory function.

        Each middleware should have the signature:
        (ctx: AnyContext, prompt: str, next: Callable[[AnyContext, str], str]) -> str

        The resulting function takes an AnyContext and returns the final prompt string.
        """

        def composed_prompt_factory(ctx: AnyContext) -> str:
            def dispatch(index: int, current_prompt: str) -> str:
                if index >= len(self._middlewares):
                    return current_prompt

                middleware = self._middlewares[index]

                def next_handler(c: AnyContext, p: str) -> str:
                    return dispatch(index + 1, p)

                return middleware(ctx, current_prompt, next_handler)

            return dispatch(0, "")

        return composed_prompt_factory


def new_prompt(new_prompt: str, render: bool = False):
    def new_prompt_middleware(
        ctx: AnyContext, current_prompt: str, next: Callable[[AnyContext, str], str]
    ):
        effective_new_prompt = new_prompt
        if render:
            effective_new_prompt = get_str_attr(ctx, new_prompt, auto_render=True)
        return next(ctx, f"{current_prompt}\n{effective_new_prompt}")

    return new_prompt_middleware
