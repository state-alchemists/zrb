from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar

from zrb.cmd.remote import bracket_ipv6


@dataclass(frozen=True)
class Host:
    """A machine commands run on: over SSH, or locally when `remote_host` is None.

    Attributes:
        name: Unique key; also selects the host.
        labels: Group names the host answers to; a string is one label.
        remote_host: SSH host. None runs the command on the machine running zrb.
        remote_port: SSH port.
        remote_user: SSH user; empty connects as the current user.
        remote_password: SSH password, sent through `sshpass` (must be installed
            where zrb runs). Hidden from `repr`. Prefer `remote_ssh_key`.
        remote_ssh_key: Path to the private key.
        cwd: Directory commands start in on the host.
        shell: Shell a local command of `zrb remote run` starts under; defaults to
            `CFG.SHELL`. A remote host and `zrb remote check` always use `sh`.
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

    Attributes:
        name: Unique key; also selects the target and heads its column.
        host: Host or IP, resolved from the *checking host*, not from zrb.
        port: TCP port; part of the URL for an http target.
        kind: `tcp` checks the port accepts connections; `http` requests the URL
            and counts any response, whatever its status code, as connected.
        scheme, path: Build the URL of an http target.
        url: Replaces the URL built from `scheme`, `host`, `port` and `path`.
        labels: Group names the target answers to; a string is one label.
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
        return self.url or (
            f"{self.scheme}://{bracket_ipv6(self.host)}:{self.port}{self.path}"
        )


def _to_labels(labels: Iterable[str]) -> frozenset[str]:
    return frozenset([labels] if isinstance(labels, str) else labels)


T = TypeVar("T", Host, Target)


class Inventory(Generic[T]):
    """Name-keyed collection of hosts or targets, selectable by label.

    `add` replaces an item of the same name. Register items in `zrb_init.py`.
    """

    def __init__(self):
        self._items: dict[str, T] = {}

    def add(self, *items: T) -> None:
        """Register items, replacing any with the same name."""
        for item in items:
            self._items[item.name] = item

    def remove(self, name: str) -> None:
        """Unregister an item; a missing name is ignored."""
        self._items.pop(name, None)

    def get_all(self) -> list[T]:
        """Every item, in registration order."""
        return list(self._items.values())

    def get_choices(self) -> list[str]:
        """Every label and name that `select` accepts, sorted."""
        names = set(self._items)
        labels = set().union(*(set(i.labels) for i in self._items.values()))
        return sorted(names | labels)

    def select(self, labels: Iterable[str] = ()) -> list[T]:
        """Items whose name or any label is in `labels`; all items if empty."""
        wanted = set(labels)
        if not wanted:
            return self.get_all()
        return [i for i in self._items.values() if wanted & (set(i.labels) | {i.name})]


host_inventory: Inventory[Host] = Inventory()
target_inventory: Inventory[Target] = Inventory()
