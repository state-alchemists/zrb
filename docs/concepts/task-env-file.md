🔖 [Table of Contents](../README.md)

# Task EnvFile

<!--start-doc-->
## `EnvFile`

Represents a handler for an environment file, facilitating the creation and management of environment variables
(Env objects) based on the contents of the specified environment file.

__Attributes:__

- `path` (`str`): The path to the environment file.
- `prefix` (`Optional[str]`): An optional prefix to be applied to environment variables.
- `should_render` (`bool`): Flag to determine if the environment values should be rendered.

__Examples:__

```python
from zrb import EnvFile, Task
import os
CURRENT_DIR = os.dirname(__file__)
task = Task(
    name='task',
    env_files=[
        EnvFile(path=os.path.join(CURRENT_DIR, '.env'), prefix='SYSTEM')
    ]
)
```


### `EnvFile.get_envs`

Retrieves a list of Env objects based on the environment file. If a prefix is provided, it is
applied to the environment variable names.

__Returns:__

`List[Env]`: A list of Env objects representing the environment variables defined in the file.

__Examples:__

```python
from zrb import Env, EnvFile
env_file = EnvFile(path='some_file.env')
envs: List[Env] = env_file.get_envs()
```


<!--end-doc-->

🔖 [Table of Contents](../README.md)
