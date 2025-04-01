# 1.5.0

- Remove `read_all_files` as it might use all token
- Roo Code style tools:
    - Rename `read_text_file` to `read_from_file`
    - Rename `write_text_file` to `write_to_file`
    - Introduce `search_files`
    - Introduce `apply_diff`
- Add `filter` parameter on todo tasks

# 1.4.3

- Update tools, use playwright if necessary

# 1.4.2

- Allow modify `default_system_prompt` via `llm_config`

# 1.4.1

- Avoid load file twice (in case of the `zrb_init.py` file in current directory is also existing on `ZRB_INIT_SCRIPTS`)
- 

# 1.4.0

- Introduce LLMConfig
- Rename tool and update signatures:
    - Rename `list_file` to `list_files`
    - Rename `read_source_code` to `read_all_files`
    - Remove parameter `extensions`, add parameters `included_patterns` and `excluded_patterns`.

# 1.3.1

- Fix CRUD filter parsing on UI
- Automatically create migration when adding new column

# 1.3.0

- Introduce `llm_chat.set_default_model`, remove `llm_chat.set_model`
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
