🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Copying Task

While building your workflow, you might notice that some of your tasks resemble each other in many ways.

Zrb allows you to copy a Task and modify a limited set of attributes.

The following are the most commonly used methods when you copy a Task:

- `copy(self)`
- `set_name(self, new_name: str)`
- `set_description(self, new_description: str)`
- `set_icon(self, new_icon: str)`
- `set_color(self, new_color: str)`
- `set_should_execute(self, should_execute: str)`
- `set_retry(self, new_retry: int)`
- `set_retry_interval(self, new_retry_interval: int)`
- `set_checking_interval(self, new_checking_retry_interval: int)`
- `insert_checker(self, *checkers: AnyTask)`
- `add_checker(self, *checkers: AnyTask)`
- `insert_upstream(self, *upstreams: AnyTask)`
- `add_upstream(self, *upstreams: AnyTask)`
- `insert_input(self, *inputs: AnyInput)`
- `add_input(self, *inputs: AnyInput)`
- `insert_env(self, *envs: Env)`
- `add_env(self, *envs: Env)`
- `insert_env_file(self, *env_files: EnvFile)`
- `add_env_file(self, *env_files: EnvFile)`

Let's see the following example:

```python
from zrb import runner, CmdTask, BoolInput

dbt_run = CmdTask(
    name='dbt-run',
    cmd='dbt run'
)

# Copying dbt run, make it skippable
skippable_dbt_run = dbt_run.copy()
skippable_dbt_run.add_input(BoolInput(name='dbt-run', default=True))
skippable_dbt_run.set_should_execute('{{ input.dbt_run }}')

# register dbt-run
runner.register(dbt_run)

# Make dbt-test depends on skippable dbt run
dbt_test = CmdTask(
    name='dbt-test',
    cmd='dbt test',
    upstreams=[skippable_dbt_run]
)
runner.register(dbt_test)
```

In the example, you create a task named `dbt-run`. You then copy the task into a variable named `skippable_dbt_run`. This new task has additional input and will be executed based on the input value.

Finally, you create another task named `dbt-test`. This task depends on `skippable_dbt_run`.

You see that despite the option to skip the execution, `dbt_run` and `skippable_dbt_run` do the same thing, and you don't need to define them twice.

# Next

For more flexibility, you can extend [Task](extending-task.md) and [CmdTask](extending-cmd-task.md)

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
