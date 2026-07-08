"""Theme-selection config."""

from __future__ import annotations

from zrb.config.env_field import EnvField
from zrb.config.theme import DEFAULT_THEME


class ThemeMixin:
    THEME = EnvField(
        str,
        default=DEFAULT_THEME,
        doc=(
            "Named style-theme preset that supplies defaults for every unset "
            "style knob (LLM UI, markdown, and CLI semantic colors). Built-in: "
            "'dark' (the historical defaults) and 'light'. Register more via "
            "zrb.config.theme.register_theme. An individually set ZRB_* style "
            "env still overrides the theme."
        ),
    )
