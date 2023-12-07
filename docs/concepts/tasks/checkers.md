🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# Checkers

Checkers are special type of tasks. You can use checkers to check for other task's readiness.

Currently there are three types of checkers:
- PathChecker
- PortChecker
- HttpChecker


Let's say you invoke `npm run build:watch`. This command will build your Node.js App into `dist` directory, as well as watch the changes and rebuild your app as soon as there are some changes.

- A web server is considered ready if it's HTTP Port is accessible. You can use `HTTPChecker` to check for web server readiness.
- But, before running the web server to start, you need to build the frontend and make sure that the `src/frontend/dist` has been created. You can use `PathChecker` to check for frontend readiness.

Let's see how we can do this:

```python
from zrb import CmdTask, PathChecker, Env, EnvFile, runner

build_frontend = CmdTask(
    name='build-frontend',
    cmd='npm run build',
    cwd='src/frontend',
    checkers=[
        PathChecker(path='src/frontend/dist')
    ]
)

run_server = CmdTask(
    name='run-server',
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    env_files=[
        EnvFile(env_file='src/template.env', prefix='WEB')
    ]
    cmd='python main.py',
    cwd='src',
    upstreams=[
        build_frontend
    ],
    checkers=[HTTPChecker(port='{{env.PORT}}')],
)
runner.register(run_server)
```

> Aside from `PathChecker` and `HTTPChecker`, you can also use `PortChecker` to check for TCP port readiness.

You can then run the server by invoking:

```bash
zrb run-server
```

# Technical Documentation

<!--start-doc-->
## `Checker`
No documentation available.


### `Checker._BaseTaskModel__get_colored`
No documentation available.

### `Checker._BaseTaskModel__get_colored_print_prefix`
No documentation available.

### `Checker._BaseTaskModel__get_common_prefix`
No documentation available.

### `Checker._BaseTaskModel__get_executable_name`
No documentation available.

### `Checker._BaseTaskModel__get_log_prefix`
No documentation available.

### `Checker._BaseTaskModel__get_print_prefix`
No documentation available.

### `Checker._BaseTaskModel__get_rjust_full_cli_name`
No documentation available.

### `Checker._Renderer__ensure_cached_render_data`
No documentation available.

### `Checker._Renderer__get_render_data`
No documentation available.

### `Checker._cached_check`
No documentation available.

### `Checker._cached_run`
No documentation available.

### `Checker._check`
Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.
### `Checker._check_should_execute`
No documentation available.

### `Checker._end_timer`
No documentation available.

### `Checker._get_attempt`
No documentation available.

### `Checker._get_checkers`
No documentation available.

### `Checker._get_combined_env`
No documentation available.

### `Checker._get_combined_inputs`
'
Getting all inputs of this task and all its upstream, non-duplicated.
### `Checker._get_elapsed_time`
No documentation available.

### `Checker._get_env_files`
No documentation available.

### `Checker._get_envs`
No documentation available.

### `Checker._get_full_cli_name`
No documentation available.

### `Checker._get_inputs`
No documentation available.

### `Checker._get_max_attempt`
No documentation available.

### `Checker._get_task_pid`
No documentation available.

### `Checker._get_upstreams`
No documentation available.

### `Checker._increase_attempt`
No documentation available.

### `Checker._is_done`
No documentation available.

### `Checker._is_last_attempt`
No documentation available.

### `Checker._lock_upstreams`
No documentation available.

### `Checker._loop_check`
No documentation available.

### `Checker._mark_awaited`
No documentation available.

### `Checker._mark_done`
No documentation available.

### `Checker._play_bell`
No documentation available.

### `Checker._print_result`
No documentation available.

### `Checker._propagate_execution_id`
No documentation available.

### `Checker._run_all`
No documentation available.

### `Checker._run_and_check_all`
No documentation available.

### `Checker._set_args`
No documentation available.

### `Checker._set_env_map`
No documentation available.

### `Checker._set_execution_id`
No documentation available.

### `Checker._set_has_cli_interface`
No documentation available.

### `Checker._set_input_map`
No documentation available.

### `Checker._set_keyval`
No documentation available.

### `Checker._set_kwargs`
No documentation available.

### `Checker._set_local_keyval`
No documentation available.

### `Checker._set_task_pid`
No documentation available.

### `Checker._should_attempt`
No documentation available.

### `Checker._show_done_info`
No documentation available.

### `Checker._show_env_prefix`
No documentation available.

### `Checker._show_run_command`
No documentation available.

### `Checker._start_timer`
No documentation available.

### `Checker.add_env`
No documentation available.

### `Checker.add_env_file`
No documentation available.

### `Checker.add_input`
No documentation available.

### `Checker.add_upstream`
No documentation available.

### `Checker.check`
No documentation available.

### `Checker.copy`
No documentation available.

### `Checker.get_cli_name`
No documentation available.

### `Checker.get_color`
No documentation available.

### `Checker.get_description`
No documentation available.

### `Checker.get_env_map`
No documentation available.

### `Checker.get_execution_id`
No documentation available.

### `Checker.get_icon`
No documentation available.

### `Checker.get_input_map`
No documentation available.

### `Checker.inject_checkers`
No documentation available.

### `Checker.inject_env_files`
No documentation available.

### `Checker.inject_envs`
No documentation available.

### `Checker.inject_inputs`
No documentation available.

### `Checker.inject_upstreams`
No documentation available.

### `Checker.insert_env`
No documentation available.

### `Checker.insert_env_file`
No documentation available.

### `Checker.insert_input`
No documentation available.

### `Checker.insert_upstream`
No documentation available.

### `Checker.inspect`
No documentation available.

### `Checker.log_critical`
No documentation available.

### `Checker.log_debug`
No documentation available.

### `Checker.log_error`
No documentation available.

### `Checker.log_info`
No documentation available.

### `Checker.log_warn`
No documentation available.

### `Checker.on_failed`
No documentation available.

### `Checker.on_ready`
No documentation available.

### `Checker.on_retry`
No documentation available.

### `Checker.on_skipped`
No documentation available.

### `Checker.on_started`
No documentation available.

### `Checker.on_triggered`
No documentation available.

### `Checker.on_waiting`
No documentation available.

### `Checker.print_err`
No documentation available.

### `Checker.print_out`
No documentation available.

### `Checker.print_out_dark`
No documentation available.

### `Checker.print_result`
No documentation available.

### `Checker.render_any`
No documentation available.

### `Checker.render_bool`
No documentation available.

### `Checker.render_file`
No documentation available.

### `Checker.render_float`
No documentation available.

### `Checker.render_int`
No documentation available.

### `Checker.render_str`
No documentation available.

### `Checker.run`
No documentation available.

### `Checker.set_checking_interval`
No documentation available.

### `Checker.set_color`
No documentation available.

### `Checker.set_description`
No documentation available.

### `Checker.set_icon`
No documentation available.

### `Checker.set_name`
No documentation available.

### `Checker.set_retry`
No documentation available.

### `Checker.set_retry_interval`
No documentation available.

### `Checker.set_should_execute`
No documentation available.

### `Checker.show_progress`
No documentation available.

### `Checker.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)