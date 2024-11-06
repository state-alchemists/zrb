import asyncio


def url_to_args(url: str) -> list[str]:
    stripped_url = url.strip("/")
    return [part for part in stripped_url.split("/") if part.strip() != ""]


def node_path_to_url(args: list[str]) -> str:
    pruned_args = [part for part in args if part.strip() != ""]
    stripped_url = "/".join(pruned_args)
    return f"/{stripped_url}/"


class SessionSnapshotCondition:
    def __init__(self):
        self._should_stop = False

    @property
    def should_stop(self) -> bool:
        return self._should_stop

    def stop(self):
        self._should_stop = True


def start_event_loop(event_loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()
