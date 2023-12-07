🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# ResourceMaker

ResourceMaker helps you create text resources, whether they are code or licenses.

For example, let's say you have the following template under `mit-license-template/license`

```
Copyright (c) <zrb_year> <zrb_copyright_holders>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

You want your user to be able to add the license to any app and replacing `<year>` and `<copyright holders>` with user input.

To accomplish this, you can make a resource maker:

```python
from zrb import ResourceMaker, StrInput, runner
import os

CURRENT_DIR = os.path.dirname(__file__)

add_mit_license = ResourceMaker(
    name='add-mit-license',
    inputs=[
        StrInput(name='destination'),
        StrInput(name='year'),
        StrInput(name='copyright-holder')
    ],
    destination_path='{{input.destination}}',
    template_path=os.path.join(CURRENT_DIR, 'mit-license-template'),
    replacements={
        '<zrb_year>': '{{input.year}}',
        '<zrb_copyright_holders>': '{{input.copyright_holder}}',
    }
)

runner.register(add_mit_license)
```

Note that your template folder might contains a very complex structure. For example, you can make your application boiler plate into a template.


# Technical Documentation

<!--start-doc-->
## `ResourceMaker`

Base class for all tasks.
Every task definition should be extended from this class.

### `ResourceMaker._BaseTaskModel__get_colored`

No documentation available.


### `ResourceMaker._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `ResourceMaker._BaseTaskModel__get_common_prefix`

No documentation available.


### `ResourceMaker._BaseTaskModel__get_executable_name`

No documentation available.


### `ResourceMaker._BaseTaskModel__get_log_prefix`

No documentation available.


### `ResourceMaker._BaseTaskModel__get_print_prefix`

No documentation available.


### `ResourceMaker._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `ResourceMaker._Renderer__ensure_cached_render_data`

No documentation available.


### `ResourceMaker._Renderer__get_render_data`

No documentation available.


### `ResourceMaker._cached_check`

No documentation available.


### `ResourceMaker._cached_run`

No documentation available.


### `ResourceMaker._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `ResourceMaker._check_should_execute`

No documentation available.


### `ResourceMaker._default_mutate_replacements`

No documentation available.


### `ResourceMaker._end_timer`

No documentation available.


### `ResourceMaker._get_attempt`

No documentation available.


### `ResourceMaker._get_checkers`

No documentation available.


### `ResourceMaker._get_combined_env`

No documentation available.


### `ResourceMaker._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `ResourceMaker._get_elapsed_time`

No documentation available.


### `ResourceMaker._get_env_files`

No documentation available.


### `ResourceMaker._get_envs`

No documentation available.


### `ResourceMaker._get_full_cli_name`

No documentation available.


### `ResourceMaker._get_inputs`

No documentation available.


### `ResourceMaker._get_max_attempt`

No documentation available.


### `ResourceMaker._get_task_pid`

No documentation available.


### `ResourceMaker._get_upstreams`

No documentation available.


### `ResourceMaker._increase_attempt`

No documentation available.


### `ResourceMaker._is_done`

No documentation available.


### `ResourceMaker._is_last_attempt`

No documentation available.


### `ResourceMaker._lock_upstreams`

No documentation available.


### `ResourceMaker._loop_check`

No documentation available.


### `ResourceMaker._mark_awaited`

No documentation available.


### `ResourceMaker._mark_done`

No documentation available.


### `ResourceMaker._play_bell`

No documentation available.


### `ResourceMaker._print_result`

No documentation available.


### `ResourceMaker._propagate_execution_id`

No documentation available.


### `ResourceMaker._run_all`

No documentation available.


### `ResourceMaker._run_and_check_all`

No documentation available.


### `ResourceMaker._set_args`

No documentation available.


### `ResourceMaker._set_env_map`

No documentation available.


### `ResourceMaker._set_execution_id`

Set current task execution id.

This method is meant for internal use.

### `ResourceMaker._set_has_cli_interface`

No documentation available.


### `ResourceMaker._set_input_map`

No documentation available.


### `ResourceMaker._set_keyval`

No documentation available.


### `ResourceMaker._set_kwargs`

No documentation available.


### `ResourceMaker._set_local_keyval`

No documentation available.


### `ResourceMaker._set_skip_parsing`

No documentation available.


### `ResourceMaker._set_task_pid`

No documentation available.


### `ResourceMaker._should_attempt`

No documentation available.


### `ResourceMaker._show_done_info`

No documentation available.


### `ResourceMaker._show_env_prefix`

No documentation available.


### `ResourceMaker._show_run_command`

No documentation available.


### `ResourceMaker._start_timer`

No documentation available.


### `ResourceMaker.add_env`

Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `ResourceMaker.add_env_file`

Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `ResourceMaker.add_input`

Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `ResourceMaker.add_upstream`

Add AnyTask to the end of the current task's upstream list.

### `ResourceMaker.check`

## Description

Define how Zrb consider current task to be ready.

You can override this method.

## Example

```python
class MyTask(Task):
async def run(self, *args: Any, **kwargs: Any) -> int:
self.print_out('Doing some calculation')
self._done = True
return 42

async def check(self) -> bool:
# When self._done is True, consider the task to be "ready"
return self._done is not None and self._done
```

### `ResourceMaker.copy`

## Description
Return copy of the current task.

You can change properties of the copied task using any of these methods:
- `set_name`
- `set_description`
- `set_icon`
- `set_color`
- `add_upstream`
- `insert_upstream`
- `add_input`
- `insert_input`
- `add_env`
- `insert_env`
- `add_env_file`
- `insert_env_file`
- or any other methods depending on the TaskClass you use.

## Example

```python
task = Task(name='my-task', cmd='echo hello')

copied_task = task.copy()
copied_task.set_name('new_name')
```

### `ResourceMaker.get_cli_name`

No documentation available.


### `ResourceMaker.get_color`

No documentation available.


### `ResourceMaker.get_description`

No documentation available.


### `ResourceMaker.get_env_map`

No documentation available.


### `ResourceMaker.get_execution_id`

No documentation available.


### `ResourceMaker.get_icon`

No documentation available.


### `ResourceMaker.get_input_map`

No documentation available.


### `ResourceMaker.inject_checkers`

No documentation available.


### `ResourceMaker.inject_env_files`

No documentation available.


### `ResourceMaker.inject_envs`

No documentation available.


### `ResourceMaker.inject_inputs`

No documentation available.


### `ResourceMaker.inject_upstreams`

No documentation available.


### `ResourceMaker.insert_env`

Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `ResourceMaker.insert_env_file`

Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `ResourceMaker.insert_input`

Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `ResourceMaker.insert_upstream`

Insert AnyTask to the beginning of the current task's upstream list.

### `ResourceMaker.log_critical`

No documentation available.


### `ResourceMaker.log_debug`

No documentation available.


### `ResourceMaker.log_error`

No documentation available.


### `ResourceMaker.log_info`

No documentation available.


### `ResourceMaker.log_warn`

No documentation available.


### `ResourceMaker.on_failed`

## Description

Define what to do when the current task status is `failed`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_failed(self, is_last_attempt: bool, exception: Exception):
if is_last_attempt:
self.print_out('The task is failed, and there will be no retry')
raise exception
self.print_out('The task is failed, going to retry')
```

### `ResourceMaker.on_ready`

## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```

### `ResourceMaker.on_retry`

## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```

### `ResourceMaker.on_skipped`

## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```

### `ResourceMaker.on_started`

## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```

### `ResourceMaker.on_triggered`

## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```

### `ResourceMaker.on_waiting`

## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```

### `ResourceMaker.print_err`

No documentation available.


### `ResourceMaker.print_out`

No documentation available.


### `ResourceMaker.print_out_dark`

No documentation available.


### `ResourceMaker.print_result`

Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.

### `ResourceMaker.render_any`

No documentation available.


### `ResourceMaker.render_bool`

No documentation available.


### `ResourceMaker.render_file`

No documentation available.


### `ResourceMaker.render_float`

No documentation available.


### `ResourceMaker.render_int`

No documentation available.


### `ResourceMaker.render_str`

No documentation available.


### `ResourceMaker.run`

## Description

Define what to do when current task is started.

You can override this method.

## Example

```python
class MyTask(Task):
async def run(self, *args: Any, **kwargs: Any) -> int:
self.print_out('Doing some calculation')
return 42
```

### `ResourceMaker.set_checking_interval`

No documentation available.


### `ResourceMaker.set_color`

No documentation available.


### `ResourceMaker.set_description`

Set current task description.
Usually used to overide copied task's description.

### `ResourceMaker.set_icon`

Set current task icon.
Usually used to overide copied task's icon.

### `ResourceMaker.set_name`

Set current task name.
Usually used to overide copied task's name.

### `ResourceMaker.set_retry`

No documentation available.


### `ResourceMaker.set_retry_interval`

No documentation available.


### `ResourceMaker.set_should_execute`

No documentation available.


### `ResourceMaker.to_function`

Turn current task into a callable.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
