# Monokai Theme Example

Demonstrates registering a **custom style theme** and selecting it with a single
env var, using zrb's `ZRB_THEME` system (ADR-0084).

## How it works

`zrb_init.py` calls `register_theme("monokai", {...})`. Registered themes are a
**partial palette merged onto the built-in `dark` theme** — you only list the
knobs you want to change, and every omitted knob keeps its `dark` value. This
example omits `LLM_UI_STYLE_BOTTOM_TOOLBAR` and all the `CLI_STYLE_*` knobs on
purpose to show the inheritance.

Knob names are `CFG` attribute names without the `ZRB_` prefix. Values are
prompt_toolkit style strings for the LLM UI, and Rich style strings for the
markdown / CLI colors.

Precedence (highest wins):

1. An explicit `ZRB_LLM_UI_STYLE_*` / `ZRB_CLI_*` env var
2. The active `ZRB_THEME` palette
3. The `dark` defaults (via the merge)

So you can pick `monokai` and still override one color by hand.

## Running the example

```bash
cd examples/themes/monokai
ZRB_THEME=monokai zrb llm chat
```

Try:
- Run without `ZRB_THEME` — you get the default `dark` theme.
- Run with `ZRB_THEME=monokai` — the whole TUI, markdown, and CLI colors switch.
- Add `ZRB_LLM_UI_STYLE_TEXT="#ffffff"` on top — your env override wins over the
  theme.

## Adding your own theme

Copy `zrb_init.py`, rename `"monokai"`, and change the values. For the full list
of knobs, see `src/zrb/config/theme.py` (the `_DARK` palette) or run
`zrb config explain` to inspect the current values.
