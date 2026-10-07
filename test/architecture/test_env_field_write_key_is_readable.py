"""Every `EnvField` must write a key it also reads.

An alias trap writes `C` while reading `A, B`, so `/set` appears successful but
subsequent reads return another value; the real `CFG` hierarchy is checked.
"""

from zrb.config.config import CFG
from zrb.config.env_field import EnvField

# The real MRO has 338 fields; 300 is the floor that exposes a broken walk.
MINIMUM_FIELDS = 300


def _config_fields() -> list[tuple[str, str, EnvField]]:
    """Return `(owner, name, descriptor)` for every `CFG` field."""
    fields = []
    for cls in type(CFG).__mro__:
        for name, attr in vars(cls).items():
            if isinstance(attr, EnvField):
                fields.append((cls.__name__, name, attr))
    return fields


def test_the_walk_reaches_the_config_fields():
    count = len(_config_fields())
    assert count >= MINIMUM_FIELDS, (
        f"only {count} `EnvField` descriptors found on `Config`'s MRO, under the "
        f"{MINIMUM_FIELDS} expected — the walk above has stopped reaching the "
        "`config/mixins/` classes, so the invariant below checks almost nothing"
    )


def test_every_field_writes_a_key_it_also_reads():
    prefix = CFG.ENV_PREFIX
    unreadable = []
    for owner, name, field in _config_fields():
        write_key = field.env_key(prefix)
        read_keys = field.get_read_keys(prefix)
        if write_key not in read_keys:
            unreadable.append(f"  {owner}.{name}: writes {write_key}, reads {read_keys}")
    assert not unreadable, (
        "These settings write to environment key(s) they never read, so "
        "assigning `CFG.<name>` (what `/set` does) stores the value where the "
        "next read cannot see it — the command confirms a change that never "
        "lands. Add the write key to `aliases`, or drop `write_key`:\n"
        + "\n".join(unreadable)
    )
