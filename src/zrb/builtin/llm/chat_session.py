import asyncio

from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_faint
from zrb.xcom.xcom import Xcom


async def read_user_prompt(ctx: AnyContext) -> str:
    final_result = ""
    result = await _trigger_ask_and_wait_for_result(
        ctx,
        user_prompt=ctx.input.message,
        previous_session=ctx.input.previous_session,
        start_new=ctx.input.start_new,
    )
    if ctx.env.get("_ZRB_WEB_ENV", "0") != "0":
        # Don't run in web environment
        if result is not None:
            final_result = result
        return final_result
    multiline_mode = False
    user_inputs = []
    while True:
        await asyncio.sleep(0.01)
        user_input = input(stylize_faint("🧑 >> "))
        # Handle special input
        if user_input.strip().lower() in ("/bye", "/quit"):
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
            if result is not None:
                final_result = result
            break
        elif user_input.strip().lower() in ("/multi"):
            multiline_mode = True
        elif user_input.strip().lower() in ("/end"):
            multiline_mode = False
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
            if result is not None:
                final_result = result
        elif user_input.strip().lower() in ("/help", "/info"):
            _show_info(ctx)
            continue
        else:
            user_inputs.append(user_input)
            if multiline_mode:
                continue
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
            if result is not None:
                final_result = result
    return final_result


async def _trigger_ask_and_wait_for_result(
    ctx: AnyContext,
    user_prompt: str,
    previous_session: str = "",
    start_new: bool = False,
) -> str | None:
    if user_prompt.strip() == "":
        return None
    _trigger_ask(ctx, user_prompt, previous_session, start_new)
    result = await _wait_llm_response(ctx)
    ctx.print(stylize_faint("🤖 >> ") + result)
    return result


def get_llm_ask_input_mapping(callback_ctx: AnyContext):
    data = callback_ctx.xcom.ask_trigger.pop()
    return {
        "model": data.get("model"),
        "base-url": data.get("base_url"),
        "api-key": data.get("api_key"),
        "system-prompt": data.get("system_prompt"),
        "start-new": data.get("start_new"),
        "previous-session": data.get("previous_session"),
        "message": data.get("message"),
    }


def _trigger_ask(
    callback_ctx: AnyContext,
    user_prompt: str,
    previous_session: str = "",
    start_new: bool = False,
):
    callback_ctx.xcom["ask_trigger"].push(
        {
            "previous_session": previous_session,
            "start_new": start_new,
            "message": user_prompt,
            "model": callback_ctx.input.model,
            "base_url": callback_ctx.input.base_url,
            "api_key": callback_ctx.input.api_key,
            "system_prompt": callback_ctx.input.system_prompt,
        }
    )


async def _wait_llm_response(ctx: AnyContext):
    if "ask_result" not in ctx.xcom:
        ctx.xcom["ask_result"] = Xcom([])
    while len(ctx.xcom.ask_result) == 0:
        await asyncio.sleep(0.1)
    return ctx.xcom.ask_result.pop()


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
