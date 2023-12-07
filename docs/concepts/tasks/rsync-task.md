🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RsyncTask

```python
from zrb import (
    runner, CmdTask, RsyncTask, RemoteConfig, PasswordInput, StrInput
)

upload = RsyncTask(
    name='upload',
    inputs=[
        PasswordInput(name='passsword'),
        StrInput(name='src'),
        StrInput(name='dst'),
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}',
            config_map={
                'dir': '192-168-1-10'
            }
        )
    ],
    is_remote_src=False,
    src='$_CONFIG_MAP_DIR/{{input.src}}',
    is_remote_dst=True,
    dst='{{input.dst}}',
)
runner.register(upload)

download = RsyncTask(
    name='download',
    inputs=[
        PasswordInput(name='passsword'),
        StrInput(name='src'),
        StrInput(name='dst'),
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    is_remote_src=True,
    src='{{input.src}}',
    is_remote_dst=False,
    dst='$_CONFIG_MAP_DIR/{{input.dst}}',
)
runner.register(download)
```

RsyncTask exposes several environments that you can use on your `src` and `dst`

- `_CONFIG_HOST`
- `_CONFIG_PORT`
- `_CONFIG_SSH_KEY`
- `_CONFIG_USER`
- `_CONFIG_PASSWORD`
- `_CONFIG_MAP_<UPPER_SNAKE_CASE_NAME>`


# Technical Documentation

<!--start-doc-->
## `RsyncTask`
No documentation available.


### `RsyncTask._BaseTaskModel__get_colored`
No documentation available.

### `RsyncTask._BaseTaskModel__get_colored_print_prefix`
No documentation available.

### `RsyncTask._BaseTaskModel__get_common_prefix`
No documentation available.

### `RsyncTask._BaseTaskModel__get_executable_name`
No documentation available.

### `RsyncTask._BaseTaskModel__get_log_prefix`
No documentation available.

### `RsyncTask._BaseTaskModel__get_print_prefix`
No documentation available.

### `RsyncTask._BaseTaskModel__get_rjust_full_cli_name`
No documentation available.

### `RsyncTask._Renderer__ensure_cached_render_data`
No documentation available.

### `RsyncTask._Renderer__get_render_data`
No documentation available.

### `RsyncTask._cached_check`
No documentation available.

### `RsyncTask._cached_run`
No documentation available.

### `RsyncTask._check`
Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.
### `RsyncTask._check_should_execute`
No documentation available.

### `RsyncTask._end_timer`
No documentation available.

### `RsyncTask._get_attempt`
No documentation available.

### `RsyncTask._get_checkers`
No documentation available.

### `RsyncTask._get_combined_env`
No documentation available.

### `RsyncTask._get_combined_inputs`
'
Getting all inputs of this task and all its upstream, non-duplicated.
### `RsyncTask._get_elapsed_time`
No documentation available.

### `RsyncTask._get_env_files`
No documentation available.

### `RsyncTask._get_envs`
No documentation available.

### `RsyncTask._get_full_cli_name`
No documentation available.

### `RsyncTask._get_inputs`
No documentation available.

### `RsyncTask._get_max_attempt`
No documentation available.

### `RsyncTask._get_parsed_path`
No documentation available.

### `RsyncTask._get_task_pid`
No documentation available.

### `RsyncTask._get_upstreams`
No documentation available.

### `RsyncTask._increase_attempt`
No documentation available.

### `RsyncTask._is_done`
No documentation available.

### `RsyncTask._is_last_attempt`
No documentation available.

### `RsyncTask._lock_upstreams`
No documentation available.

### `RsyncTask._loop_check`
No documentation available.

### `RsyncTask._mark_awaited`
No documentation available.

### `RsyncTask._mark_done`
No documentation available.

### `RsyncTask._play_bell`
No documentation available.

### `RsyncTask._print_result`
No documentation available.

### `RsyncTask._propagate_execution_id`
No documentation available.

### `RsyncTask._run_all`
No documentation available.

### `RsyncTask._run_and_check_all`
No documentation available.

### `RsyncTask._set_args`
No documentation available.

### `RsyncTask._set_env_map`
No documentation available.

### `RsyncTask._set_execution_id`
No documentation available.

### `RsyncTask._set_has_cli_interface`
No documentation available.

### `RsyncTask._set_input_map`
No documentation available.

### `RsyncTask._set_keyval`
No documentation available.

### `RsyncTask._set_kwargs`
No documentation available.

### `RsyncTask._set_local_keyval`
No documentation available.

### `RsyncTask._set_task_pid`
No documentation available.

### `RsyncTask._should_attempt`
No documentation available.

### `RsyncTask._show_done_info`
No documentation available.

### `RsyncTask._show_env_prefix`
No documentation available.

### `RsyncTask._show_run_command`
No documentation available.

### `RsyncTask._start_timer`
No documentation available.

### `RsyncTask.add_env`
No documentation available.

### `RsyncTask.add_env_file`
No documentation available.

### `RsyncTask.add_input`
No documentation available.

### `RsyncTask.add_upstream`
No documentation available.

### `RsyncTask.check`
No documentation available.

### `RsyncTask.copy`
No documentation available.

### `RsyncTask.get_cli_name`
No documentation available.

### `RsyncTask.get_color`
No documentation available.

### `RsyncTask.get_description`
No documentation available.

### `RsyncTask.get_env_map`
No documentation available.

### `RsyncTask.get_execution_id`
No documentation available.

### `RsyncTask.get_icon`
No documentation available.

### `RsyncTask.get_input_map`
No documentation available.

### `RsyncTask.inject_checkers`
No documentation available.

### `RsyncTask.inject_env_files`
No documentation available.

### `RsyncTask.inject_envs`
No documentation available.

### `RsyncTask.inject_inputs`
No documentation available.

### `RsyncTask.inject_upstreams`
No documentation available.

### `RsyncTask.insert_env`
No documentation available.

### `RsyncTask.insert_env_file`
No documentation available.

### `RsyncTask.insert_input`
No documentation available.

### `RsyncTask.insert_upstream`
No documentation available.

### `RsyncTask.log_critical`
No documentation available.

### `RsyncTask.log_debug`
No documentation available.

### `RsyncTask.log_error`
No documentation available.

### `RsyncTask.log_info`
No documentation available.

### `RsyncTask.log_warn`
No documentation available.

### `RsyncTask.on_failed`
No documentation available.

### `RsyncTask.on_ready`
No documentation available.

### `RsyncTask.on_retry`
No documentation available.

### `RsyncTask.on_skipped`
No documentation available.

### `RsyncTask.on_started`
No documentation available.

### `RsyncTask.on_triggered`
No documentation available.

### `RsyncTask.on_waiting`
No documentation available.

### `RsyncTask.print_err`
No documentation available.

### `RsyncTask.print_out`
No documentation available.

### `RsyncTask.print_out_dark`
No documentation available.

### `RsyncTask.print_result`
No documentation available.

### `RsyncTask.render_any`
No documentation available.

### `RsyncTask.render_bool`
No documentation available.

### `RsyncTask.render_file`
No documentation available.

### `RsyncTask.render_float`
No documentation available.

### `RsyncTask.render_int`
No documentation available.

### `RsyncTask.render_str`
No documentation available.

### `RsyncTask.run`
No documentation available.

### `RsyncTask.set_checking_interval`
No documentation available.

### `RsyncTask.set_color`
No documentation available.

### `RsyncTask.set_description`
No documentation available.

### `RsyncTask.set_icon`
No documentation available.

### `RsyncTask.set_name`
No documentation available.

### `RsyncTask.set_retry`
No documentation available.

### `RsyncTask.set_retry_interval`
No documentation available.

### `RsyncTask.set_should_execute`
No documentation available.

### `RsyncTask.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
