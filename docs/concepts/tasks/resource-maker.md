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
No documentation available.


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
No documentation available.

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
No documentation available.

### `ResourceMaker.add_env_file`
No documentation available.

### `ResourceMaker.add_input`
No documentation available.

### `ResourceMaker.add_upstream`
No documentation available.

### `ResourceMaker.check`
No documentation available.

### `ResourceMaker.copy`
No documentation available.

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
No documentation available.

### `ResourceMaker.insert_env_file`
No documentation available.

### `ResourceMaker.insert_input`
No documentation available.

### `ResourceMaker.insert_upstream`
No documentation available.

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
No documentation available.

### `ResourceMaker.on_ready`
No documentation available.

### `ResourceMaker.on_retry`
No documentation available.

### `ResourceMaker.on_skipped`
No documentation available.

### `ResourceMaker.on_started`
No documentation available.

### `ResourceMaker.on_triggered`
No documentation available.

### `ResourceMaker.on_waiting`
No documentation available.

### `ResourceMaker.print_err`
No documentation available.

### `ResourceMaker.print_out`
No documentation available.

### `ResourceMaker.print_out_dark`
No documentation available.

### `ResourceMaker.print_result`
No documentation available.

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
No documentation available.

### `ResourceMaker.set_checking_interval`
No documentation available.

### `ResourceMaker.set_color`
No documentation available.

### `ResourceMaker.set_description`
No documentation available.

### `ResourceMaker.set_icon`
No documentation available.

### `ResourceMaker.set_name`
No documentation available.

### `ResourceMaker.set_retry`
No documentation available.

### `ResourceMaker.set_retry_interval`
No documentation available.

### `ResourceMaker.set_should_execute`
No documentation available.

### `ResourceMaker.to_function`
No documentation available.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
