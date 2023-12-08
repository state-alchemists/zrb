🔖 [Table of Contents](../README.md)

# Task Env

<!--start-doc-->
## `Env`

Env Represents an environment configuration for a task, encapsulating details such as environment name, OS-specific
environment name, default values, and rendering behavior.

__Attributes:__

- `name` (`str`): Environment name as recognized by the task.
- `os_name` (`Optional[str]`): The corresponding name in the OS's environment, if different from 'name'. You can set os_name to empty string if you don't want the environment to be linked to OS environment name.
- `default` (`JinjaTemplate`): Default value of the environment variable.
- `should_render` (`bool`): Flag to determine if the environment value should be rendered.

__Examples:__

```python
from zrb import Env, Task
task = Task(
    name='task',
    envs=[
        Env(name='DATABASE_URL', os_name='SYSTEM_DATABASE_URL', default='postgresql://...')
    ]
)
```


### `Env._Env__get_prefixed_name`

Constructs the prefixed name of the environment variable.

This method is intended for internal use only.

__Arguments:__

- `name` (`str`): The base name of the environment variable.
- `prefix` (`str`): The prefix to be added to the name.

__Returns:__

`str`: The prefixed name of the environment variable.

### `Env.get`

Retrieves the value of the environment variable, considering an optional prefix.

__Arguments:__

- `prefix` (`str`): An optional prefix to distinguish different environments (e.g., 'DEV', 'PROD').

__Returns:__

`str`: The value of the environment variable, considering the prefix and default value.

__Examples:__

```python
from zrb import Env
import os
os.environ['DEV_SERVER'] = 'localhost'
os.environ['PROD_SERVER'] = 'example.com'
env = Env(name='HOST', os_name='SERVER', default='0.0.0.0')
print(env.get('DEV'))   # will show 'localhost'
print(env.get('PROD'))  # will show 'example.com'
print(env.get('STAG'))  # will show '0.0.0.0'
```


### `Env.get_default`

Retrieves the default value of the environment variable.

__Returns:__

`str`: The default value of the environment variable.

### `Env.get_name`

Retrieves the name of the environment variable.

__Returns:__

`str`: The name of the environment variable.

### `Env.get_os_name`

Retrieves the OS-specific name of the environment variable.

__Returns:__

`Optional[str]`: The OS-specific name of the environment variable.

### `Env.should_render`

Determines whether the environment value should be rendered.

__Returns:__

`bool`: True if the environment value should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../README.md)
