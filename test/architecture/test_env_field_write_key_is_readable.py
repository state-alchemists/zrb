"""Every `EnvField` must write to an environment key it also reads.

`CFG.<name> = value` stores under the field's *write* key, and a read tries the
field's read keys in order. When the two sets do not overlap the assignment
looks like it worked — the value is in `os.environ` under the write key, and
`/set` confirms it — while the next read falls through to an alias, the default,
or the `DEFAULT_<NAME>` attribute and returns something else entirely. That is
the whole of the `/set` alias trap: a field reads `A, B` and writes `C`, so
`/set` reports a change the setting never receives.

`EnvField.__set_name__` removes the possibility by moving the write key to the
front of the read list — but only when the write key is already one of the
aliases. A field that names a `write_key` outside its `aliases` (or outside
`[name]` when `aliases` is omitted) reopens it, and nothing else notices. The
two token-limit settings are the live example: they read singular or plural and
write the plural form, which is why the ordering in `__set_name__` is
load-bearing rather than cosmetic.

Checked against the real `CFG` hierarchy, not a fixture: a synthetic host may
legitimately model an asymmetric field, and `test/config/test_env_field.py`
deliberately keeps one to pin the write-key semantics.
"""

from zrb.config.config import CFG
from zrb.config.env_field import EnvField

# Every `EnvField` on the `Config` MRO, counted so a hierarchy refactor that
# stops the walk cannot leave this file green while checking nothing. The real
# count is 338 across the `config/mixins/` classes; the floor only has to be
# high enough that a broken walk is obvious.
MINIMUM_FIELDS = 300


def _config_fields() -> list[tuple[str, str, EnvField]]:
    """`(owning class, attribute name, descriptor)` for every `CFG` field."""
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
