"""Every user-settable `CFG` knob is named on a live documentation page.

A knob is public surface: it is read from an environment variable or set in
`zrb_init.py`, and `zrb config explain` prints it. A knob that no page names is
therefore a feature a reader cannot discover, and it is exactly the gap a
review misses, because the code and the prose live in different files.

`docs/adr/` and `docs/changelog/` are excluded: an ADR records why a decision
was made and a changelog records what shipped, so a name that appears only
there is frozen history, not the reference a user opens. `docs/configuration/`
is the usual home; a knob whose explanation belongs on a feature page
(`/sandbox`'s command aliases in `docs/llm/sandbox.md`) is documented there.

The check is coverage, not a row format: a table row, a prose paragraph and a
code sample all satisfy it. The floor below is a scan sanity check, not a
ratchet — knobs are removed as well as added.
"""

import pathlib
import re

from zrb.config.config import CFG
from zrb.config.env_field import EnvField

REPO_ROOT = pathlib.Path(__file__).parents[2]
DOCS = REPO_ROOT / "docs"
FROZEN_DIRS = {"adr", "changelog"}


def _knob_keys() -> dict[str, str]:
    """Every `EnvField` attribute, mapped to the env key a user sets."""
    keys: dict[str, str] = {}
    for cls in type(CFG).__mro__:
        for name, value in vars(cls).items():
            if isinstance(value, EnvField):
                keys[name] = value.env_key(CFG.ENV_PREFIX)
    return keys


def _live_docs() -> list[str]:
    return [
        path.read_text(encoding="utf-8")
        for path in sorted(DOCS.rglob("*.md"))
        if not FROZEN_DIRS & set(path.relative_to(DOCS).parts)
    ]


def test_every_config_knob_is_named_in_a_live_doc():
    keys = _knob_keys()
    docs = _live_docs()
    patterns = {
        key: re.compile(rf"(?<![A-Z0-9_]){re.escape(key)}(?![A-Z0-9_])")
        for key in keys.values()
    }
    missing = sorted(
        key
        for key, pattern in patterns.items()
        if not any(pattern.search(text) for text in docs)
    )
    assert not missing, (
        "These settings are user-settable and no live doc names them; add each "
        "to the page that owns it (usually docs/configuration/): " + ", ".join(missing)
    )


def test_the_scan_reaches_the_configuration_surface():
    """A scan that finds no fields would pass the check above vacuously."""
    assert len(_knob_keys()) > 300, (
        "The `CFG` walk found almost no `EnvField`s; the mixins moved or the "
        "MRO changed, and the coverage check is now blind."
    )
