"""Which built-in hooks a run registers.

A built-in hook is on unless its name is listed in `LLM_HOOKS_DISABLED`. The
list exists because the alternative — one boolean per hook — cannot grow past
the second hook without becoming a wall of near-identical flags, and because a
hook that cannot be switched off individually forces the whole subsystem off.
`HOOKS_ENABLED` stays the single switch for everything; this one is the scalpel.
"""

from zrb.config.config import CFG


def is_builtin_hook_enabled(name: str) -> bool:
    """Whether the built-in hook *name* should be registered.

    A name is matched exactly. Blank entries (a trailing comma, a stray space)
    are dropped rather than treated as a name nobody has.
    """
    listed = CFG.LLM_HOOKS_DISABLED or []
    disabled = {str(part).strip() for part in listed if str(part).strip()}
    return name not in disabled
