# 1.2.3

- Introduce `always_prompt` parameter for input

# 1.2.2

- Fix and refactor FastApp CRUD


# 1.2.1

- Fixing Fastapp generator by adding `os.path.abspath`

# 1.2.0

- When creating any `Input`, use `default` keyword instead of `default_str`.

# 1.1.0

- Fastapp generator is now generating UI when user add new columns (i.e., `zrb project <app-name> create column`)
- Zrb is now loading `zrb_init.py` from parent directories as well, so you can have `zrb_init.py` in your home directory.

# 1.0.0

- Big rewrite, there are major incaompatibility with version `0.x.x`