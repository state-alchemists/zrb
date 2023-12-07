🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# DockerComposeTask

Docker Compose is a convenient way to run containers on your local computer.

Suppose you have the following Docker Compose file:

```yaml
# docker-compose.yml file
version: '3'

services:
  # The load balancer
  nginx:
    image: nginx:1.16.0-alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "${HOST_PORT:-8080}:80"
```

You can define a task to run your Docker Compose file (i.e., `docker compose up`) like this:

```python
from zrb import DockerComposeTask, HTTPChecker, Env, runner

run_container = DockerComposeTask(
    name='run-container',
    compose_cmd='up',
    compose_file='docker-compose.yml',
    envs=[
        Env(name='HOST_PORT', default='3000')
    ],
    checkers=[
        HTTPChecker(
            name='check-readiness', port='{{env.HOST_PORT}}'
        )
    ]
)
runner.register(run_container)
```

You can then run the task by invoking:

```bash
zrb run-container
```

Under the hood, Zrb will read your `compose_file` populate it with some additional configuration, and create a runtime compose file `._<compose-file>-<task-name>.runtime.yml`. Zrb will use the run the runtime compose file to run your `compose_cmd` (i.e., `docker compose -f <compose-file>-<task-name>.runtime.yml <compose-cmd>`)


# Technical Documentation

<!--start-doc-->
## `DockerComposeTask`
No documentation available.


### `DockerComposeTask._BaseTaskModel__get_colored`
No documentation available.

### `DockerComposeTask._BaseTaskModel__get_colored_print_prefix`
No documentation available.

### `DockerComposeTask._BaseTaskModel__get_common_prefix`
No documentation available.

### `DockerComposeTask._BaseTaskModel__get_executable_name`
No documentation available.

### `DockerComposeTask._BaseTaskModel__get_log_prefix`
No documentation available.

### `DockerComposeTask._BaseTaskModel__get_print_prefix`
No documentation available.

### `DockerComposeTask._BaseTaskModel__get_rjust_full_cli_name`
No documentation available.

### `DockerComposeTask._CmdTask__add_to_buffer`
No documentation available.

### `DockerComposeTask._CmdTask__get_multiline_repr`
No documentation available.

### `DockerComposeTask._CmdTask__get_rendered_cmd`
No documentation available.

### `DockerComposeTask._CmdTask__get_rendered_cmd_path`
No documentation available.

### `DockerComposeTask._CmdTask__is_process_exist`
No documentation available.

### `DockerComposeTask._CmdTask__kill_by_pid`
Kill a pid, gracefully
### `DockerComposeTask._CmdTask__log_from_queue`
No documentation available.

### `DockerComposeTask._CmdTask__on_exit`
No documentation available.

### `DockerComposeTask._CmdTask__on_kill`
No documentation available.

### `DockerComposeTask._CmdTask__queue_stream`
No documentation available.

### `DockerComposeTask._CmdTask__set_cwd`
No documentation available.

### `DockerComposeTask._CmdTask__wait_process`
No documentation available.

### `DockerComposeTask._DockerComposeTask__apply_service_env`
No documentation available.

### `DockerComposeTask._DockerComposeTask__generate_compose_runtime_file`
No documentation available.

### `DockerComposeTask._DockerComposeTask__get_compose_runtime_file`
No documentation available.

### `DockerComposeTask._DockerComposeTask__get_compose_template_file`
No documentation available.

### `DockerComposeTask._DockerComposeTask__get_env_compose_value`
No documentation available.

### `DockerComposeTask._DockerComposeTask__get_service_new_env_list`
No documentation available.

### `DockerComposeTask._DockerComposeTask__get_service_new_env_map`
No documentation available.

### `DockerComposeTask._Renderer__ensure_cached_render_data`
No documentation available.

### `DockerComposeTask._Renderer__get_render_data`
No documentation available.

### `DockerComposeTask._cached_check`
No documentation available.

### `DockerComposeTask._cached_run`
No documentation available.

### `DockerComposeTask._check`
Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.
### `DockerComposeTask._check_should_execute`
No documentation available.

### `DockerComposeTask._create_cmd_script`
No documentation available.

### `DockerComposeTask._end_timer`
No documentation available.

### `DockerComposeTask._get_attempt`
No documentation available.

### `DockerComposeTask._get_checkers`
No documentation available.

### `DockerComposeTask._get_combined_env`
No documentation available.

### `DockerComposeTask._get_combined_inputs`
'
Getting all inputs of this task and all its upstream, non-duplicated.
### `DockerComposeTask._get_elapsed_time`
No documentation available.

### `DockerComposeTask._get_env_files`
No documentation available.

### `DockerComposeTask._get_envs`
No documentation available.

### `DockerComposeTask._get_full_cli_name`
No documentation available.

### `DockerComposeTask._get_inputs`
No documentation available.

### `DockerComposeTask._get_max_attempt`
No documentation available.

### `DockerComposeTask._get_task_pid`
No documentation available.

### `DockerComposeTask._get_upstreams`
No documentation available.

### `DockerComposeTask._increase_attempt`
No documentation available.

### `DockerComposeTask._is_done`
No documentation available.

### `DockerComposeTask._is_last_attempt`
No documentation available.

### `DockerComposeTask._lock_upstreams`
No documentation available.

### `DockerComposeTask._loop_check`
No documentation available.

### `DockerComposeTask._mark_awaited`
No documentation available.

### `DockerComposeTask._mark_done`
No documentation available.

### `DockerComposeTask._play_bell`
No documentation available.

### `DockerComposeTask._print_result`
No documentation available.

### `DockerComposeTask._propagate_execution_id`
No documentation available.

### `DockerComposeTask._run_all`
No documentation available.

### `DockerComposeTask._run_and_check_all`
No documentation available.

### `DockerComposeTask._set_args`
No documentation available.

### `DockerComposeTask._set_env_map`
No documentation available.

### `DockerComposeTask._set_execution_id`
No documentation available.

### `DockerComposeTask._set_has_cli_interface`
No documentation available.

### `DockerComposeTask._set_input_map`
No documentation available.

### `DockerComposeTask._set_keyval`
No documentation available.

### `DockerComposeTask._set_kwargs`
No documentation available.

### `DockerComposeTask._set_local_keyval`
No documentation available.

### `DockerComposeTask._set_task_pid`
No documentation available.

### `DockerComposeTask._should_attempt`
No documentation available.

### `DockerComposeTask._show_done_info`
No documentation available.

### `DockerComposeTask._show_env_prefix`
No documentation available.

### `DockerComposeTask._show_run_command`
No documentation available.

### `DockerComposeTask._start_timer`
No documentation available.

### `DockerComposeTask.add_env`
No documentation available.

### `DockerComposeTask.add_env_file`
No documentation available.

### `DockerComposeTask.add_input`
No documentation available.

### `DockerComposeTask.add_upstream`
No documentation available.

### `DockerComposeTask.check`
No documentation available.

### `DockerComposeTask.copy`
No documentation available.

### `DockerComposeTask.get_cli_name`
No documentation available.

### `DockerComposeTask.get_cmd_script`
No documentation available.

### `DockerComposeTask.get_color`
No documentation available.

### `DockerComposeTask.get_description`
No documentation available.

### `DockerComposeTask.get_env_map`
No documentation available.

### `DockerComposeTask.get_execution_id`
No documentation available.

### `DockerComposeTask.get_icon`
No documentation available.

### `DockerComposeTask.get_input_map`
No documentation available.

### `DockerComposeTask.inject_checkers`
No documentation available.

### `DockerComposeTask.inject_env_files`
No documentation available.

### `DockerComposeTask.inject_envs`
No documentation available.

### `DockerComposeTask.inject_inputs`
No documentation available.

### `DockerComposeTask.inject_upstreams`
No documentation available.

### `DockerComposeTask.insert_env`
No documentation available.

### `DockerComposeTask.insert_env_file`
No documentation available.

### `DockerComposeTask.insert_input`
No documentation available.

### `DockerComposeTask.insert_upstream`
No documentation available.

### `DockerComposeTask.log_critical`
No documentation available.

### `DockerComposeTask.log_debug`
No documentation available.

### `DockerComposeTask.log_error`
No documentation available.

### `DockerComposeTask.log_info`
No documentation available.

### `DockerComposeTask.log_warn`
No documentation available.

### `DockerComposeTask.on_failed`
No documentation available.

### `DockerComposeTask.on_ready`
No documentation available.

### `DockerComposeTask.on_retry`
No documentation available.

### `DockerComposeTask.on_skipped`
No documentation available.

### `DockerComposeTask.on_started`
No documentation available.

### `DockerComposeTask.on_triggered`
No documentation available.

### `DockerComposeTask.on_waiting`
No documentation available.

### `DockerComposeTask.print_err`
No documentation available.

### `DockerComposeTask.print_out`
No documentation available.

### `DockerComposeTask.print_out_dark`
No documentation available.

### `DockerComposeTask.print_result`
No documentation available.

### `DockerComposeTask.render_any`
No documentation available.

### `DockerComposeTask.render_bool`
No documentation available.

### `DockerComposeTask.render_file`
No documentation available.

### `DockerComposeTask.render_float`
No documentation available.

### `DockerComposeTask.render_int`
No documentation available.

### `DockerComposeTask.render_str`
No documentation available.

### `DockerComposeTask.run`
No documentation available.

### `DockerComposeTask.set_checking_interval`
No documentation available.

### `DockerComposeTask.set_color`
No documentation available.

### `DockerComposeTask.set_cwd`
No documentation available.

### `DockerComposeTask.set_description`
No documentation available.

### `DockerComposeTask.set_icon`
No documentation available.

### `DockerComposeTask.set_name`
No documentation available.

### `DockerComposeTask.set_retry`
No documentation available.

### `DockerComposeTask.set_retry_interval`
No documentation available.

### `DockerComposeTask.set_should_execute`
No documentation available.

### `DockerComposeTask.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)