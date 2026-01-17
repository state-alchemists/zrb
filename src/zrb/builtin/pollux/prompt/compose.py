from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.util.attr import get_str_attr

PromptMiddleware = Callable[[AnyContext, str, Callable[[AnyContext, str], str]], str]


def compose_prompt(
    *middlewares: PromptMiddleware,
) -> Callable[[AnyContext], str]:
    """
    Composes a list of prompt middlewares into a single prompt factory function.

    Each middleware should have the signature:
    (ctx: AnyContext, prompt: str, next: Callable[[AnyContext, str], str]) -> str

    The resulting function takes an AnyContext and returns the final prompt string.
    """

    def composed_prompt_factory(ctx: AnyContext) -> str:
        def dispatch(index: int, current_prompt: str) -> str:
            if index >= len(middlewares):
                return current_prompt

            middleware = middlewares[index]

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
