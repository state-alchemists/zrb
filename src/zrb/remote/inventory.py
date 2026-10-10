from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar


@dataclass(frozen=True)
class Host:
    """A machine commands run on: over SSH, or locally when `remote_host` is None.

    The `remote_*` fields mean what they do on `CmdTask`. `labels` select the
    host from `zrb remote` tasks; the name also selects it.
    """

    name: str
    labels: Iterable[str] = frozenset()
    remote_host: str | None = None
    remote_port: int = 22
    remote_user: str = ""
    remote_password: str = field(default="", repr=False)
    remote_ssh_key: str = ""
    cwd: str | None = None
    shell: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "labels", _to_labels(self.labels))


@dataclass(frozen=True)
class Target:
    """An endpoint hosts are checked against: a TCP port or an HTTP(S) URL.

    `url`, when set, replaces the one built from `scheme`, `host`, `port`
    and `path`.
    """

    name: str
    host: str = ""
    port: int = 80
    kind: Literal["tcp", "http"] = "tcp"
    scheme: Literal["http", "https"] = "http"
    path: str = "/"
    url: str = ""
    labels: Iterable[str] = frozenset()

    def __post_init__(self):
        object.__setattr__(self, "labels", _to_labels(self.labels))
        if self.kind == "http" and self.url == "" and self.host == "":
            raise ValueError(f"Target {self.name!r}: an http target needs host or url")
        if self.kind == "tcp" and self.host == "":
            raise ValueError(f"Target {self.name!r}: a tcp target needs host")

    def get_url(self) -> str:
        """The URL probed for an http target."""
        return self.url or f"{self.scheme}://{self.host}:{self.port}{self.path}"


def _to_labels(labels: Iterable[str]) -> frozenset[str]:
    return frozenset([labels] if isinstance(labels, str) else labels)


T = TypeVar("T", Host, Target)


class Inventory(Generic[T]):
    """Name-keyed collection of hosts or targets, selectable by label."""

    def __init__(self):
        self._items: dict[str, T] = {}

    def add(self, *items: T) -> None:
        for item in items:
            self._items[item.name] = item

    def remove(self, name: str) -> None:
        self._items.pop(name, None)

    def get_all(self) -> list[T]:
        return list(self._items.values())

    def get_labels(self) -> list[str]:
        """Every label in use, sorted."""
        return sorted(set().union(*(set(i.labels) for i in self._items.values())))

    def select(self, labels: Iterable[str] = ()) -> list[T]:
        """Items whose name or any label is in `labels`; all items if empty."""
        wanted = set(labels)
        if not wanted:
            return self.get_all()
        return [i for i in self._items.values() if wanted & (set(i.labels) | {i.name})]


host_inventory: Inventory[Host] = Inventory()
target_inventory: Inventory[Target] = Inventory()
