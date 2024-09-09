import asyncio

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.helper.asyncio_task", attrs=["dark"]))


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
        else:
            loop.run_until_complete(stop_asyncio())
    except Exception:
        pass
