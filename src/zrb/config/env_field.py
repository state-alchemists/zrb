"""`EnvField`: a data descriptor that maps a config attribute to an env var.

Collapses the repetitive get_env/cast getter + os.environ setter pattern that
every `CFG.*` knob otherwise hand-writes. Reads honor `aliases`, convert with
`cast`, and fall back to `default_factory(host)`, an explicit `default`, or the
host's `DEFAULT_<NAME>` attribute (in that order). Writes go to `os.environ`
under `write_key` (defaults to the attribute name), serialized with `serialize`;
writing ``None`` removes the var when `nullable` is set.

Public access stays flat and unchanged: `CFG.LLM_MODEL` resolves through the
descriptor exactly as a `@property` did, so no caller or test needs to change.

Genuinely irregular knobs are intentionally NOT migrated and stay as
hand-written properties: non-prefixed env keys (foundation's `ENV_PREFIX`,
`VERSION`; search `BRAVE_API_KEY`/`SERPAPI_KEY`), and values needing
post-read transformation (`BANNER`, `LLM_ASSISTANT_NAME`).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Generic, TypeVar, overload

from zrb.config.helper import get_env

T = TypeVar("T")
_UNSET = object()


def on_off(value: Any) -> str:
    """Serialize a bool to the ``on``/``off`` form the existing setters wrote."""
    return "on" if value else "off"


def colon_list(raw: str) -> list[str]:
    """Parse a ``:``-delimited string, stripping and dropping empty segments."""
    return [part.strip() for part in raw.split(":") if part.strip() != ""]


def expanduser_colon_list(raw: str) -> list[str]:
    """Like `colon_list` but `~`-expands each entry (matches LLM_PLUGIN_DIRS)."""
    return [
        os.path.expanduser(part.strip())
        for part in raw.split(":")
        if part.strip() != ""
    ]


def comma_list(raw: str) -> list[str]:
    """Parse a ``,``-delimited string, stripping and dropping empty segments."""
    return [part.strip() for part in raw.split(",") if part.strip() != ""]


def colon_join(value: list[str]) -> str:
    return ":".join(value)


def comma_join(value: list[str]) -> str:
    return ",".join(value)


class EnvField(Generic[T]):
    """Descriptor mapping a `CFG` attribute to a prefixed environment variable.

    Parameters
    ----------
    cast:
        Callable applied to the raw string on read (e.g. ``int``, ``float``,
        ``to_boolean``, ``colon_list``). Defaults to ``str`` (identity).
    transform:
        Optional ``callable(value, host) -> value`` applied after ``cast``.
        Receives the already-cast value and the host config object, enabling
        post-read transformations that depend on sibling config (e.g. clamping
        a token threshold against ``LLM_MAX_TOKEN_PER_MINUTE``).
    serialize:
        Callable applied to the value on write before storing in os.environ
        (e.g. ``on_off``, ``colon_join``). Defaults to ``str``.
    aliases:
        Env-var names (without prefix) to try in order on read. Defaults to
        ``[attribute_name]``.
    write_key:
        Env-var name (without prefix) the setter writes to. Defaults to the
        attribute name. Use this when read and write keys differ.
    default:
        Explicit fallback string when no env var is set. Takes precedence over
        the ``DEFAULT_<NAME>`` attribute but not over ``default_factory``.
    default_factory:
        ``callable(host) -> str`` computing the fallback at read time (for
        defaults that depend on other config, e.g. a dir derived from
        ``ROOT_GROUP_NAME``). Highest precedence.
    fallback:
        Value returned when ``cast`` raises ``ValueError`` or ``TypeError``
        (e.g. an env var set to ``"abc"`` with ``cast=int``). Lets fields
        degrade gracefully instead of raising. Unset by default (re-raises).
    nullable:
        When ``True``, an unset/empty value reads as ``None`` and assigning
        ``None`` deletes the env var instead of writing ``"None"``.
    doc:
        Docstring surfaced as the descriptor's ``__doc__``.
    """

    def __init__(
        self,
        cast: Callable[[str], T] = str,  # type: ignore[assignment]
        *,
        transform: Callable[[T, Any], T] | None = None,
        serialize: Callable[[Any], str] = str,
        aliases: list[str] | None = None,
        write_key: str | None = None,
        default: Any = _UNSET,
        default_factory: Callable[[Any], str] | None = None,
        fallback: Any = _UNSET,
        nullable: bool = False,
        doc: str = "",
    ):
        self._cast = cast
        self._transform = transform
        self._serialize = serialize
        self._aliases = aliases
        self._write_key = write_key
        self._default = default
        self._default_factory = default_factory
        self._fallback = fallback
        self._nullable = nullable
        self.__doc__ = doc

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name
        self._read_names = self._aliases if self._aliases is not None else [name]
        self._write_name = self._write_key if self._write_key is not None else name

    def _resolve_default(self, obj: Any) -> str:
        if self._default_factory is not None:
            return self._default_factory(obj)
        if self._default is not _UNSET:
            return self._default
        return getattr(obj, f"DEFAULT_{self._name}", "")

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> "EnvField[T]": ...

    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> T: ...

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        raw = get_env(self._read_names, self._resolve_default(obj), obj.ENV_PREFIX)
        if self._nullable and not raw:
            return None
        if not raw:
            # An explicitly empty env var (e.g. `export ZRB_WEB_HTTP_PORT=`) would
            # otherwise reach a typed cast such as int("")/to_boolean("") and
            # raise an opaque error. Treat empty the same as unset and fall back
            # to the resolved default, which is known-castable. (Nullable fields
            # already short-circuit above; a str-cast field with an empty default
            # is unaffected since str("") == "".)
            raw = self._resolve_default(obj)
        try:
            value = self._cast(raw)
        except (ValueError, TypeError):
            if self._fallback is not _UNSET:
                return self._fallback
            raise
        if self._transform is not None:
            value = self._transform(value, obj)
        return value

    def __set__(self, obj: Any, value: Any) -> None:
        key = f"{obj.ENV_PREFIX}_{self._write_name}"
        if value is None and self._nullable:
            os.environ.pop(key, None)
            return
        os.environ[key] = self._serialize(value)
