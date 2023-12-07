🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# CmdTask

You can use CmdTask to run CLI commands.

Let's see the following example:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd='echo {{input.name}}'
)
runner.register(say_hello)
```

If you need a multi-line command, you can also define the command as a list:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd=[
        'echo {{input.name}}',
        'echo $_INPUT_NAME', # This will also works
        'echo Yeay!!!'
    ]
)
runner.register(say_hello)
```

However, if your command is too long, you can also load it from another file:


```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd_path='hello_script.sh'
)
runner.register(say_hello)
```

You can then run the task by invoking:

```bash
zrb say-hello --name=John
```

# Technical Documentation

<!--start-doc-->
## `CmdTask`
Command Task.
You can use this task to run shell command.

For example:
```python
# run a simple task
hello = CmdTask(
name='hello',
inputs=[StrInput(name='name', default='World')],
envs=[Env(name='HOME_DIR', os_name='HOME')],
cmd=[
'echo Hello {{ input.name }}',
'echo Home directory is: $HOME_DIR',
]
)
runner.register(hello)

# run a long running process
run_server = CmdTask(
name='run',
inputs=[StrInput(name='dir', default='.')],
envs=[Env(name='PORT', os_name='WEB_PORT', default='3000')],
cmd='python -m http.server $PORT --directory {{input.dir}}',
checkers=[HTTPChecker(port='{{env.PORT}}')]
)
runner.register(run_server)
```

### `CmdTask._BaseTaskModel__get_colored`
No documentation available.

### `CmdTask._BaseTaskModel__get_colored_print_prefix`
No documentation available.

### `CmdTask._BaseTaskModel__get_common_prefix`
No documentation available.

### `CmdTask._BaseTaskModel__get_executable_name`
No documentation available.

### `CmdTask._BaseTaskModel__get_log_prefix`
No documentation available.

### `CmdTask._BaseTaskModel__get_print_prefix`
No documentation available.

### `CmdTask._BaseTaskModel__get_rjust_full_cli_name`
No documentation available.

### `CmdTask._CmdTask__add_to_buffer`
No documentation available.

### `CmdTask._CmdTask__get_multiline_repr`
No documentation available.

### `CmdTask._CmdTask__get_rendered_cmd`
No documentation available.

### `CmdTask._CmdTask__get_rendered_cmd_path`
No documentation available.

### `CmdTask._CmdTask__is_process_exist`
No documentation available.

### `CmdTask._CmdTask__kill_by_pid`
Kill a pid, gracefully
### `CmdTask._CmdTask__log_from_queue`
No documentation available.

### `CmdTask._CmdTask__on_exit`
No documentation available.

### `CmdTask._CmdTask__on_kill`
No documentation available.

### `CmdTask._CmdTask__queue_stream`
No documentation available.

### `CmdTask._CmdTask__set_cwd`
No documentation available.

### `CmdTask._CmdTask__wait_process`
No documentation available.

### `CmdTask._Renderer__ensure_cached_render_data`
No documentation available.

### `CmdTask._Renderer__get_render_data`
No documentation available.

### `CmdTask._cached_check`
No documentation available.

### `CmdTask._cached_run`
No documentation available.

### `CmdTask._check`
Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.
### `CmdTask._check_should_execute`
No documentation available.

### `CmdTask._create_cmd_script`
No documentation available.

### `CmdTask._end_timer`
No documentation available.

### `CmdTask._get_attempt`
No documentation available.

### `CmdTask._get_checkers`
No documentation available.

### `CmdTask._get_combined_env`
No documentation available.

### `CmdTask._get_combined_inputs`
'
Getting all inputs of this task and all its upstream, non-duplicated.
### `CmdTask._get_elapsed_time`
No documentation available.

### `CmdTask._get_env_files`
No documentation available.

### `CmdTask._get_envs`
No documentation available.

### `CmdTask._get_full_cli_name`
No documentation available.

### `CmdTask._get_inputs`
No documentation available.

### `CmdTask._get_max_attempt`
No documentation available.

### `CmdTask._get_task_pid`
No documentation available.

### `CmdTask._get_upstreams`
No documentation available.

### `CmdTask._increase_attempt`
No documentation available.

### `CmdTask._is_done`
No documentation available.

### `CmdTask._is_last_attempt`
No documentation available.

### `CmdTask._lock_upstreams`
No documentation available.

### `CmdTask._loop_check`
No documentation available.

### `CmdTask._mark_awaited`
No documentation available.

### `CmdTask._mark_done`
No documentation available.

### `CmdTask._play_bell`
No documentation available.

### `CmdTask._print_result`
No documentation available.

### `CmdTask._propagate_execution_id`
No documentation available.

### `CmdTask._run_all`
No documentation available.

### `CmdTask._run_and_check_all`
No documentation available.

### `CmdTask._set_args`
No documentation available.

### `CmdTask._set_env_map`
No documentation available.

### `CmdTask._set_execution_id`
No documentation available.

### `CmdTask._set_has_cli_interface`
No documentation available.

### `CmdTask._set_input_map`
No documentation available.

### `CmdTask._set_keyval`
No documentation available.

### `CmdTask._set_kwargs`
No documentation available.

### `CmdTask._set_local_keyval`
No documentation available.

### `CmdTask._set_task_pid`
No documentation available.

### `CmdTask._should_attempt`
No documentation available.

### `CmdTask._show_done_info`
No documentation available.

### `CmdTask._show_env_prefix`
No documentation available.

### `CmdTask._show_run_command`
No documentation available.

### `CmdTask._start_timer`
No documentation available.

### `CmdTask.add_env`
No documentation available.

### `CmdTask.add_env_file`
No documentation available.

### `CmdTask.add_input`
No documentation available.

### `CmdTask.add_upstream`
No documentation available.

### `CmdTask.check`
No documentation available.

### `CmdTask.copy`
No documentation available.

### `CmdTask.get_cli_name`
No documentation available.

### `CmdTask.get_cmd_script`
No documentation available.

### `CmdTask.get_color`
No documentation available.

### `CmdTask.get_description`
No documentation available.

### `CmdTask.get_env_map`
No documentation available.

### `CmdTask.get_execution_id`
No documentation available.

### `CmdTask.get_icon`
No documentation available.

### `CmdTask.get_input_map`
No documentation available.

### `CmdTask.inject_checkers`
No documentation available.

### `CmdTask.inject_env_files`
No documentation available.

### `CmdTask.inject_envs`
No documentation available.

### `CmdTask.inject_inputs`
No documentation available.

### `CmdTask.inject_upstreams`
No documentation available.

### `CmdTask.insert_env`
No documentation available.

### `CmdTask.insert_env_file`
No documentation available.

### `CmdTask.insert_input`
No documentation available.

### `CmdTask.insert_upstream`
No documentation available.

### `CmdTask.log_critical`
No documentation available.

### `CmdTask.log_debug`
No documentation available.

### `CmdTask.log_error`
No documentation available.

### `CmdTask.log_info`
No documentation available.

### `CmdTask.log_warn`
No documentation available.

### `CmdTask.on_failed`
No documentation available.

### `CmdTask.on_ready`
No documentation available.

### `CmdTask.on_retry`
No documentation available.

### `CmdTask.on_skipped`
No documentation available.

### `CmdTask.on_started`
No documentation available.

### `CmdTask.on_triggered`
No documentation available.

### `CmdTask.on_waiting`
No documentation available.

### `CmdTask.print_err`
No documentation available.

### `CmdTask.print_out`
No documentation available.

### `CmdTask.print_out_dark`
No documentation available.

### `CmdTask.print_result`
No documentation available.

### `CmdTask.render_any`
No documentation available.

### `CmdTask.render_bool`
No documentation available.

### `CmdTask.render_file`
No documentation available.

### `CmdTask.render_float`
No documentation available.

### `CmdTask.render_int`
No documentation available.

### `CmdTask.render_str`
No documentation available.

### `CmdTask.run`
No documentation available.

### `CmdTask.set_checking_interval`
No documentation available.

### `CmdTask.set_color`
No documentation available.

### `CmdTask.set_cwd`
No documentation available.

### `CmdTask.set_description`
No documentation available.

### `CmdTask.set_icon`
No documentation available.

### `CmdTask.set_name`
No documentation available.

### `CmdTask.set_retry`
No documentation available.

### `CmdTask.set_retry_interval`
No documentation available.

### `CmdTask.set_should_execute`
No documentation available.

### `CmdTask.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
