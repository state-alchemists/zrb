
🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# FlowTask

FlowTask allows you to compose several unrelated tasks/actions into a single tasks.

```python
from zrb import FlowTask, CmdTask, HttpChecker, runner
import os

CURRENT_DIR = os.dirname(__file__)

prepare_backend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(CURRENT_DIR, 'app', 'backend'),
    cmd='pip install -r requirements.txt'
)

prepare_frontend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(CURRENT_DIR, 'app', 'frontend'),
    cmd='npm install && npm run build'
)

start_app = CmdTask(
    name='start-app',
    cwd=os.path.join(CURRENT_DIR, 'app', 'backend'),
    cmd='uvicorn main:app --port 8080',
    checkers=[
        HttpChecker(port=8080)
    ]
)

prepare_and_start_app = FlowTask(
    name='prepare-and-start-app',
    steps=[
        # Prepare backend and frontend concurrently
        [
            prepare_backend,
            prepare_frontend
        ],
        # Then start app
        start_app,
        # And finally show instruction
        CmdTask(
            name='show-instruction',
            cmd='echo "App is ready, Check your browser"'
        )
    ]
)
runner.register(prepare_app)
```

# Technical Documentation

<!--start-doc-->
## `FlowTask`
No documentation available.


### `FlowTask._BaseTaskModel__get_colored`
No documentation available.

### `FlowTask._BaseTaskModel__get_colored_print_prefix`
No documentation available.

### `FlowTask._BaseTaskModel__get_common_prefix`
No documentation available.

### `FlowTask._BaseTaskModel__get_executable_name`
No documentation available.

### `FlowTask._BaseTaskModel__get_log_prefix`
No documentation available.

### `FlowTask._BaseTaskModel__get_print_prefix`
No documentation available.

### `FlowTask._BaseTaskModel__get_rjust_full_cli_name`
No documentation available.

### `FlowTask._Renderer__ensure_cached_render_data`
No documentation available.

### `FlowTask._Renderer__get_render_data`
No documentation available.

### `FlowTask._cached_check`
No documentation available.

### `FlowTask._cached_run`
No documentation available.

### `FlowTask._check`
Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.
### `FlowTask._check_should_execute`
No documentation available.

### `FlowTask._end_timer`
No documentation available.

### `FlowTask._get_attempt`
No documentation available.

### `FlowTask._get_checkers`
No documentation available.

### `FlowTask._get_combined_env`
No documentation available.

### `FlowTask._get_combined_inputs`
'
Getting all inputs of this task and all its upstream, non-duplicated.
### `FlowTask._get_elapsed_time`
No documentation available.

### `FlowTask._get_embeded_tasks`
No documentation available.

### `FlowTask._get_env_files`
No documentation available.

### `FlowTask._get_envs`
No documentation available.

### `FlowTask._get_full_cli_name`
No documentation available.

### `FlowTask._get_inputs`
No documentation available.

### `FlowTask._get_max_attempt`
No documentation available.

### `FlowTask._get_task_pid`
No documentation available.

### `FlowTask._get_upstreams`
No documentation available.

### `FlowTask._increase_attempt`
No documentation available.

### `FlowTask._is_done`
No documentation available.

### `FlowTask._is_last_attempt`
No documentation available.

### `FlowTask._lock_upstreams`
No documentation available.

### `FlowTask._loop_check`
No documentation available.

### `FlowTask._mark_awaited`
No documentation available.

### `FlowTask._mark_done`
No documentation available.

### `FlowTask._play_bell`
No documentation available.

### `FlowTask._print_result`
No documentation available.

### `FlowTask._propagate_execution_id`
No documentation available.

### `FlowTask._run_all`
No documentation available.

### `FlowTask._run_and_check_all`
No documentation available.

### `FlowTask._set_args`
No documentation available.

### `FlowTask._set_env_map`
No documentation available.

### `FlowTask._set_execution_id`
No documentation available.

### `FlowTask._set_has_cli_interface`
No documentation available.

### `FlowTask._set_input_map`
No documentation available.

### `FlowTask._set_keyval`
No documentation available.

### `FlowTask._set_kwargs`
No documentation available.

### `FlowTask._set_local_keyval`
No documentation available.

### `FlowTask._set_task_pid`
No documentation available.

### `FlowTask._should_attempt`
No documentation available.

### `FlowTask._show_done_info`
No documentation available.

### `FlowTask._show_env_prefix`
No documentation available.

### `FlowTask._show_run_command`
No documentation available.

### `FlowTask._start_timer`
No documentation available.

### `FlowTask._step_to_tasks`
No documentation available.

### `FlowTask.add_env`
No documentation available.

### `FlowTask.add_env_file`
No documentation available.

### `FlowTask.add_input`
No documentation available.

### `FlowTask.add_upstream`
No documentation available.

### `FlowTask.check`
No documentation available.

### `FlowTask.copy`
No documentation available.

### `FlowTask.get_cli_name`
No documentation available.

### `FlowTask.get_color`
No documentation available.

### `FlowTask.get_description`
No documentation available.

### `FlowTask.get_env_map`
No documentation available.

### `FlowTask.get_execution_id`
No documentation available.

### `FlowTask.get_icon`
No documentation available.

### `FlowTask.get_input_map`
No documentation available.

### `FlowTask.inject_checkers`
No documentation available.

### `FlowTask.inject_env_files`
No documentation available.

### `FlowTask.inject_envs`
No documentation available.

### `FlowTask.inject_inputs`
No documentation available.

### `FlowTask.inject_upstreams`
No documentation available.

### `FlowTask.insert_env`
No documentation available.

### `FlowTask.insert_env_file`
No documentation available.

### `FlowTask.insert_input`
No documentation available.

### `FlowTask.insert_upstream`
No documentation available.

### `FlowTask.log_critical`
No documentation available.

### `FlowTask.log_debug`
No documentation available.

### `FlowTask.log_error`
No documentation available.

### `FlowTask.log_info`
No documentation available.

### `FlowTask.log_warn`
No documentation available.

### `FlowTask.on_failed`
No documentation available.

### `FlowTask.on_ready`
No documentation available.

### `FlowTask.on_retry`
No documentation available.

### `FlowTask.on_skipped`
No documentation available.

### `FlowTask.on_started`
No documentation available.

### `FlowTask.on_triggered`
No documentation available.

### `FlowTask.on_waiting`
No documentation available.

### `FlowTask.print_err`
No documentation available.

### `FlowTask.print_out`
No documentation available.

### `FlowTask.print_out_dark`
No documentation available.

### `FlowTask.print_result`
No documentation available.

### `FlowTask.render_any`
No documentation available.

### `FlowTask.render_bool`
No documentation available.

### `FlowTask.render_file`
No documentation available.

### `FlowTask.render_float`
No documentation available.

### `FlowTask.render_int`
No documentation available.

### `FlowTask.render_str`
No documentation available.

### `FlowTask.run`
No documentation available.

### `FlowTask.set_checking_interval`
No documentation available.

### `FlowTask.set_color`
No documentation available.

### `FlowTask.set_description`
No documentation available.

### `FlowTask.set_icon`
No documentation available.

### `FlowTask.set_name`
No documentation available.

### `FlowTask.set_retry`
No documentation available.

### `FlowTask.set_retry_interval`
No documentation available.

### `FlowTask.set_should_execute`
No documentation available.

### `FlowTask.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)