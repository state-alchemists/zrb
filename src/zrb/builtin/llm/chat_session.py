import asyncio

from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_faint


async def read_user_prompt(ctx: AnyContext) -> str:
    _maybe_push_user_prompt(
        ctx,
        user_prompt=ctx.input.message,
        previous_session=ctx.input.previous_session,
        start_new=ctx.input.start_new,
    )
    if ctx.env.get("_ZRB_WEB_ENV", "0") != "0":
        # Don't run in web environment
        return ctx.xcom.pop("llm-chat")
    multiline_mode = False
    messages = []
    while True:
        await asyncio.sleep(5)
        user_input = input(stylize_faint(">> "))
        # Handle special input
        if user_input.strip().lower() in ("/bye", "/quit"):
            _maybe_push_user_prompt(ctx, "\n".join(messages))
            break
        elif user_input.strip().lower() in ("/multi"):
            multiline_mode = True
        elif user_input.strip().lower() in ("/end"):
            multiline_mode = False
            _maybe_push_user_prompt(ctx, "\n".join(messages))
        elif user_input.strip().lower() in ("/help", "/info"):
            _show_info(ctx)
            continue
        else:
            messages.append(user_input)
            if not multiline_mode:
                _maybe_push_user_prompt(ctx, "\n".join(messages))


def _maybe_push_user_prompt(
    ctx: AnyContext,
    user_prompt: str,
    previous_session: str = "",
    start_new: bool = False,
):
    if user_prompt.strip() == "":
        return
    ctx.xcom["chat_trigger"].push(
        {
            "previous_session": previous_session,
            "start_new": start_new,
            "message": user_prompt,
            "model": ctx.input.model,
            "base_url": ctx.input.base_url,
            "api_key": ctx.input.api_key,
            "system_prompt": ctx.input.system_prompt,
        }
    )


def _show_info(ctx: AnyContext):
    ctx.print(
        stylize_faint(
            "\n".join(
                [
                    "/bye:   Quit from chat session",
                    "/multi: Start multiline input",
                    "/end:   End multiline input",
                    "/help:  Show this message",
                ]
            )
        )
    )
