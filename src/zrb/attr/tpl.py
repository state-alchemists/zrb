"""Explicit template wrapper.

Rendering is opt-in: a bare `str` passed to any task attribute is a literal
value, never a template. Wrap it in `Tpl` to have it rendered against the
active context when the attribute is resolved.

    CmdTask(cmd=Tpl("echo {ctx.input.name}"))

`Tpl` is resolved through the same branch as any other callable — `get_attr`
dispatches on `callable(attr)` — so it needs no special handling and fits the
existing `Callable[..., str]` arm of every `*Attr` alias.

Prefer `Tpl` over a lambda when the value comes from the context, since a
closure captures the *variable* and not its value:

    for name in names:
        CmdTask(cmd=lambda ctx: f"echo {name}")  # every task echoes the last name
        CmdTask(cmd=Tpl(f"echo {name}"))         # f-string binds name eagerly
"""

from zrb.context.any_shared_context import AnySharedContext


class Tpl:
    """A template string rendered against the context when resolved."""

    def __init__(self, template: str):
        """Wrap `template` for deferred rendering.

        Args:
            template: An f-string-style template. Expressions in `{}` are
                evaluated against the context by `AnySharedContext.render`.
        """
        self._template = template

    @property
    def template(self) -> str:
        """The unrendered template string."""
        return self._template

    def __call__(self, ctx: AnySharedContext) -> str:
        """Render the template against `ctx`."""
        return ctx.render(self._template)

    def __repr__(self) -> str:
        return f"Tpl({self._template!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Tpl):
            return self._template == other.template
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._template))
