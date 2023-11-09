🔖 [Table of Contents](README.md)

# Quirks

- Zrb is spelled `Zaruba`.
- If not set, `PYTHONUNBUFFERED` will be set to `1`.
- Once `zrb_init.py` is loaded, Zrb will automatically:
    - Set `ZRB_PROJECT_DIR` to `zrb_init.py`'s parent directory.
    - If loaded as CLI, Zrb will also:
        - Adding `ZRB_PROJECT_DIR` to `PYTHONPATH`.
- Zrb passes several keyword arguments that will be accessible from the task's run method:
    - `_args`: Shell argument when the task is invoked.
    - `_task`: Reference to the current task.
- You can access the built-in command groups by importing `zrb.builtin.group`.
- How environments are loaded:
    - `env_files` has the lowest priority, it will be overridden by `env`
        - The last one takes greater priority
    - `env` will override each other, the last one takes greater priority
    - If you define a `DockerComposeTask`, it will automatically fill your environment with the ones you use in your docker-compose file. The environment defined that way will have a very low priority. They will be overridden by both `env_files` and `env`.
- You cannot have an input named: `_task`, `_args` or `_execution_id`

🔖 [Table of Contents](README.md)
