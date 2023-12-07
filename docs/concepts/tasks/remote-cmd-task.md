🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RemoteCmdTask

```python
from zrb import (
    runner, CmdTask, RemoteCmdTask, RemoteConfig, PasswordInput
)

install_curl = RemoteCmdTask(
    name='install-curl',
    inputs=[
        PasswordInput(name='passsword')
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    cmd=[
        'sudo apt update',
        'sudo apt install curl --y'
    ]
)
runner.register(install_curl)
```

RemoteCmdTask exposes several environments that you can use on your `cmd` and `cmd_path`

- `_CONFIG_HOST`
- `_CONFIG_PORT`
- `_CONFIG_SSH_KEY`
- `_CONFIG_USER`
- `_CONFIG_PASSWORD`
- `_CONFIG_MAP_<UPPER_SNAKE_CASE_NAME>`


# Technical Documentation

<!--start-doc-->
## `RemoteCmdTask`
No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_colored`
No documentation available.

### `RemoteCmdTask._BaseTaskModel__get_colored_print_prefix`
No documentation available.

### `RemoteCmdTask._BaseTaskModel__get_common_prefix`
No documentation available.

### `RemoteCmdTask._BaseTaskModel__get_executable_name`
No documentation available.

### `RemoteCmdTask._BaseTaskModel__get_log_prefix`
No documentation available.

### `RemoteCmdTask._BaseTaskModel__get_print_prefix`
No documentation available.

### `RemoteCmdTask._BaseTaskModel__get_rjust_full_cli_name`
No documentation available.

### `RemoteCmdTask._Renderer__ensure_cached_render_data`
No documentation available.

### `RemoteCmdTask._Renderer__get_render_data`
No documentation available.

### `RemoteCmdTask._cached_check`
No documentation available.

### `RemoteCmdTask._cached_run`
No documentation available.

### `RemoteCmdTask._check`
Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.
### `RemoteCmdTask._check_should_execute`
No documentation available.

### `RemoteCmdTask._end_timer`
No documentation available.

### `RemoteCmdTask._get_attempt`
No documentation available.

### `RemoteCmdTask._get_checkers`
No documentation available.

### `RemoteCmdTask._get_combined_env`
No documentation available.

### `RemoteCmdTask._get_combined_inputs`
'
Getting all inputs of this task and all its upstream, non-duplicated.
### `RemoteCmdTask._get_elapsed_time`
No documentation available.

### `RemoteCmdTask._get_env_files`
No documentation available.

### `RemoteCmdTask._get_envs`
No documentation available.

### `RemoteCmdTask._get_full_cli_name`
No documentation available.

### `RemoteCmdTask._get_inputs`
No documentation available.

### `RemoteCmdTask._get_max_attempt`
No documentation available.

### `RemoteCmdTask._get_task_pid`
No documentation available.

### `RemoteCmdTask._get_upstreams`
No documentation available.

### `RemoteCmdTask._increase_attempt`
No documentation available.

### `RemoteCmdTask._is_done`
No documentation available.

### `RemoteCmdTask._is_last_attempt`
No documentation available.

### `RemoteCmdTask._lock_upstreams`
No documentation available.

### `RemoteCmdTask._loop_check`
No documentation available.

### `RemoteCmdTask._mark_awaited`
No documentation available.

### `RemoteCmdTask._mark_done`
No documentation available.

### `RemoteCmdTask._play_bell`
No documentation available.

### `RemoteCmdTask._print_result`
No documentation available.

### `RemoteCmdTask._propagate_execution_id`
No documentation available.

### `RemoteCmdTask._run_all`
No documentation available.

### `RemoteCmdTask._run_and_check_all`
No documentation available.

### `RemoteCmdTask._set_args`
No documentation available.

### `RemoteCmdTask._set_env_map`
No documentation available.

### `RemoteCmdTask._set_execution_id`
No documentation available.

### `RemoteCmdTask._set_has_cli_interface`
No documentation available.

### `RemoteCmdTask._set_input_map`
No documentation available.

### `RemoteCmdTask._set_keyval`
No documentation available.

### `RemoteCmdTask._set_kwargs`
No documentation available.

### `RemoteCmdTask._set_local_keyval`
No documentation available.

### `RemoteCmdTask._set_task_pid`
No documentation available.

### `RemoteCmdTask._should_attempt`
No documentation available.

### `RemoteCmdTask._show_done_info`
No documentation available.

### `RemoteCmdTask._show_env_prefix`
No documentation available.

### `RemoteCmdTask._show_run_command`
No documentation available.

### `RemoteCmdTask._start_timer`
No documentation available.

### `RemoteCmdTask.add_env`
No documentation available.

### `RemoteCmdTask.add_env_file`
No documentation available.

### `RemoteCmdTask.add_input`
No documentation available.

### `RemoteCmdTask.add_upstream`
No documentation available.

### `RemoteCmdTask.check`
No documentation available.

### `RemoteCmdTask.copy`
No documentation available.

### `RemoteCmdTask.get_cli_name`
No documentation available.

### `RemoteCmdTask.get_color`
No documentation available.

### `RemoteCmdTask.get_description`
No documentation available.

### `RemoteCmdTask.get_env_map`
No documentation available.

### `RemoteCmdTask.get_execution_id`
No documentation available.

### `RemoteCmdTask.get_icon`
No documentation available.

### `RemoteCmdTask.get_input_map`
No documentation available.

### `RemoteCmdTask.inject_checkers`
No documentation available.

### `RemoteCmdTask.inject_env_files`
No documentation available.

### `RemoteCmdTask.inject_envs`
No documentation available.

### `RemoteCmdTask.inject_inputs`
No documentation available.

### `RemoteCmdTask.inject_upstreams`
No documentation available.

### `RemoteCmdTask.insert_env`
No documentation available.

### `RemoteCmdTask.insert_env_file`
No documentation available.

### `RemoteCmdTask.insert_input`
No documentation available.

### `RemoteCmdTask.insert_upstream`
No documentation available.

### `RemoteCmdTask.log_critical`
No documentation available.

### `RemoteCmdTask.log_debug`
No documentation available.

### `RemoteCmdTask.log_error`
No documentation available.

### `RemoteCmdTask.log_info`
No documentation available.

### `RemoteCmdTask.log_warn`
No documentation available.

### `RemoteCmdTask.on_failed`
No documentation available.

### `RemoteCmdTask.on_ready`
No documentation available.

### `RemoteCmdTask.on_retry`
No documentation available.

### `RemoteCmdTask.on_skipped`
No documentation available.

### `RemoteCmdTask.on_started`
No documentation available.

### `RemoteCmdTask.on_triggered`
No documentation available.

### `RemoteCmdTask.on_waiting`
No documentation available.

### `RemoteCmdTask.print_err`
No documentation available.

### `RemoteCmdTask.print_out`
No documentation available.

### `RemoteCmdTask.print_out_dark`
No documentation available.

### `RemoteCmdTask.print_result`
No documentation available.

### `RemoteCmdTask.render_any`
No documentation available.

### `RemoteCmdTask.render_bool`
No documentation available.

### `RemoteCmdTask.render_file`
No documentation available.

### `RemoteCmdTask.render_float`
No documentation available.

### `RemoteCmdTask.render_int`
No documentation available.

### `RemoteCmdTask.render_str`
No documentation available.

### `RemoteCmdTask.run`
No documentation available.

### `RemoteCmdTask.set_checking_interval`
No documentation available.

### `RemoteCmdTask.set_color`
No documentation available.

### `RemoteCmdTask.set_description`
No documentation available.

### `RemoteCmdTask.set_icon`
No documentation available.

### `RemoteCmdTask.set_name`
No documentation available.

### `RemoteCmdTask.set_retry`
No documentation available.

### `RemoteCmdTask.set_retry_interval`
No documentation available.

### `RemoteCmdTask.set_should_execute`
No documentation available.

### `RemoteCmdTask.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
