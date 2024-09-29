import asyncio
import sys

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.helper.asyncio_task", attrs=["dark"]))


def _surpress_event_loop_error(unraisable):
    if not (
        isinstance(unraisable.exc_value, RuntimeError)
        and str(unraisable.exc_value) == "Event loop is closed"
    ):
        # Raise exception for anything except "event loop is closed"
        sys.__unraisablehook__(unraisable)


sys.unraisablehook = _surpress_event_loop_error


async def stop_asyncio():
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    # Wait until all tasks are cancelled
    await asyncio.gather(*tasks, return_exceptions=True)


def stop_asyncio_sync():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(stop_asyncio())
    except asyncio.CancelledError:
        logger.warning("Task is cancelled")
