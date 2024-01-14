🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Environments

<div align="center">
  <img src="../_images/emoji/palm_tree.png"/>
  <p>
    <sub>
      Save the Earth. It's the only planet with chocolate!
    </sub>
  </p>
</div>


You can use `envs` and `env_files` attributes to define Task Environments.

Let's see the following example:

```python
from zrb import runner, Env, CmdTask

hello = CmdTask(
    name='hello',
    envs=[
        Env(
            name='USER_NAME',
            os_name='USER',
            default='Employee'
        )
    ],
    cmd='echo Hello $USER_NAME',
)
runner.register(hello)
```

In the example, you define an environment named `USER_NAME`. This environment is linked to the operating system `USER` environment. If the value of the `USER` environment is not set, Zrb will use the default value `Employee`.

If you don't provide `os_name`, Zrb will link your environment to the Operating System environment environment with the same name.

You can set `os_name` to an empty string (i.e., `''`) to avoid association with the operating system's environment. If you set `os_name` to empty, then Zrb will always use the `default` value of the environment.

To access the environment variable, you can use `$USER_NAME`. Alternatively, you can also use the Jinja Template `{{ env.USER_NAME }}`.

As for `@python_task`, you can access Task Environment using `kwargs['_task'].get_env_map()`. Let's see the following example:


```python
from zrb import runner, Env, python_task, Task

@python_task(
    name='hello',
    envs=[
        Env(
            name='USER_NAME',
            os_name='USER',
            default='Employee'
        )
    ],
    runner=runner
)
def hello(*args, **kwargs) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    user_name = env_map.get('USER_NAME')
    return f'Hello {user_name}'
```

Notice that Zrb is not altering your `os.environ`, so you cannot use a typical `os.getenv('USER_NAME')` here. This behavior is intentional since we want every Task to be isolated from each other.

There are some parameters you can use to define an `Env`.

- __name__: Name of the environment variable (required).
- __os_name__: Name of OS environment (optional, default=`None`)
    - If set to `None`, Zrb will link the environment variable to the OS environment.
    - If set to an empty string (i.e., `''`), Zrb will not link the environment variable to the OS's environment.
    - If set to a non-empty string, Zrb will link the environment variable to the OS's environment corresponding to this value.
- __default__: Default value of the environment variable (optional, default: `None`).
- __should_render__: Whether the environment variable should be rendered as a Jinja template (optional, default: `True`).


# Using Environment File

<div align="center">
  <img src="../_images/emoji/desert_island.png"/>
  <p>
    <sub>
      An island is just a sea's attempt at a mountain peak joke.
    </sub>
  </p>
</div>


As with `cmd` and `cmd_path` in `CmdTask`, Zrb also allows you to load external environment files. You can use `env_files` attributes for this.

Unlike `cmd_path` and `cmd`, `env` and `env_files` are complementing each other. You can use both attributes in a single Task. As a general rule, `env` will override `env_file`.

Suppose you have an environment file as follows:

```bash
# file-name: .env
DBT_PROFILE=dbt-profile
```

You can load the environments defined in the file as follows:


```python
from zrb import runner, Env, EnvFile, CmdTask
import os

CURRENT_DIR = os.dirname(__file__)

hello = CmdTask(
    name='hello',
    envs=[
        Env(
            name='USER_NAME',
            os_name='USER',
            default='Employee'
        )
    ],
    env_files=[
        EnvFile(path=os.path.join(CURRENT_DIR, '.env'))
    ],
    cmd=[
        'echo "Username: $USER_NAME"',
        'echo "DBT Profile: $DBT_PROFILE"'
    ]
)
runner.register(hello)
```

As for `@python_task`, you can use the same methods


```python
from zrb import runner, Env, EnvFile, python_task, Task
import os

CURRENT_DIR = os.dirname(__file__)

@python_task(
    name='hello',
    envs=[
        Env(
            name='USER_NAME',
            os_name='USER',
            default='Employee'
        )
    ],
    env_files=[
        EnvFile(path=os.path.join(CURRENT_DIR, '.env'))
    ],
    runner=runner
)
def hello(*args, **kwargs) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    user_name = env_map.get('USER_NAME')
    dbt_profile = env_map.get('DBT_PROFILE')
    return '\n'.join([
        f'Username: {user_name}',
        f'DBT Profile: {dbt_profile}'
    ])
```

There are some parameters you can use to define an `EnvFile`.

- __env_file__: Name of the environment file (required).
- __prefix__: Custom prefix for environment's os_name (optional, default=`None`)
- __should_render__: Whether the environment variable should be rendered as a Jinja template (optional, default: `True`).

# Environment Cascading

<div align="center">
  <img src="../_images/emoji/fountain.png"/>
  <p>
    <sub>
      Cascading: Nature's way of saying, 'Let's take this step by step, but faster!'
    </sub>
  </p>
</div>


We usually work on multiple environments (e.g., `dev`, `staging`, and `production`).

With environment cascading, you can switch your working environment seamlessly by setting up `ZRB_ENV`.

Let's say you need an environment named `BASE_URL`, and you need to check whether the `BASE_URL` is accessible or not.

The value of the `BASE_URL` depends on which working environment you are currently in.
- For production, `BASE_URL` should be `https://your-company.com`
- For staging, `BASE_URL` should be `https://staging.your-company.com`
- For dev, `BASE_URL` should be `https://dev.your-company.com`
- For any other working environment, `BASE_URL` should be `http://localhost:8080`

To do this, let's make an environment file `.env`:

```bash
export BASE_URL=http://localhost:8080
export DEV_BASE_URL=https://dev.your-company.com
export STAGING_BASE_URL=https://staging.your-company.com
export PROD_BASE_URL=https://your-company.com
```

Notice how you define several `BASE_URL` with `DEV`, `STAGING`, and `PROD` prefixes. You will need these prefixes to distinguish one working environment from another.

Once you create the environment files, you can use a `python_task` to check the accessibility of the `BASE_URL`.

```python
from zrb import runner, python_task, Task, Env

@python_task(
    name='check',
    envs=[
        Env(name='BASE_URL')
    ],
    runner=runner
)
def check(*args, **kwargs):
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    url = env_map.get('BASE_URL')
    task.print_out(f'Checking {url}')
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
        task.print_err('Non OK status')
        return False
    except requests.ConnectionError:
        task.print_err('Connection error')
        return False
    except requests.RequestException:
        task.print_err('Request exception')
        return False
    except Exception:
        task.print_err('Unknown exception')
        return False
```

Now you can load the environment file and switch between working environments

```bash
# Load the environments from .env
source .env

export ZRB_ENV=LOCAL
zrb check # Will check on http://localhost:8080

export ZRB_ENV=PROD
zrb check # Will check on https://your-company.com

export ZRB_ENV=STAGING
zrb check # Will check on https://staging.your-company.com

export ZRB_ENV=DEV
zrb check # Will check on https://dev.your-company.com

export ZRB_ENV=UNKNOWN
zrb check # Will check on http://localhost:8080
```

You can see that the value of `BASE_URL` will be used if Zrb cannot find any environment matching the `ZRB_ENV` prefix (i.e., we don't have `LOCAL_BASE_URL` and `UNKNOWN_BASE_URL` in our `.env`).

To see the more detailed visualization, please look at the following table:

| ZRB_ENV | BASE_URL                           | <ZRB_ENV>_BASE_URL                                    | Final                            |
|---------|------------------------------------|-------------------------------------------------------|----------------------------------|
| PROD    | BASE_URL=http://localhost:8080     | PROD_BASE_URL=**https://your-company.com**            | https://your-company.com         |
| STAGING | BASE_URL=http://localhost:8080     | STAGING_BASE_URL=**https://staging.your-company.com** | https://staging.your-company.com |
| DEV     | BASE_URL=http://localhost:8080     | DEV_BASE_URL=**https://dev.your-company.com**         | https://dev.your-company.com     |
| LOCAL   | BASE_URL=**http://localhost:8080** | LOCAL_BASE_URL=                                       | http://localhost:8080            |
| UNKNOWN | BASE_URL=**http://localhost:8080** | UNKNOWN_BASE_URL=                                     | http://localhost:8080            |

Environment cascading is handy if you need to work with multiple working environments.

# Conflicting Environment

If you declare multiple environments with the same name, the latter overrides the previous ones. Also, `envs` takes greater priority than `env_files`. That's mean that you can always override `env_files` with `envs`.


Suppose you have two environment files, `a.env`, and `b.env`:

```bash
# file-name: a.env

export PLANET=Mercury
export ELEMENT=Air
export GOD=Hermes
```

```bash
# file-name: b.env

export PLANET=Mars
export ELEMENT=Fire
```

You also have the following Task definition:

```bash
from zrb import runner, CmdTask, Env, EnvFile

show = CmdTask(
    name='show',
    env_files=[
        EnvFile(path='a.env'),
        EnvFile(path='b.env'), # b.env override a.env
    ],
    envs=[
        Env(name='PLANET', os_name='', default='Venus') # Override Mercury and Mars
        Env(name='PLANET', os_name='', default='Jupiter') # Override Venus 
    ],
    cmd=[
        'echo "GOD: $GOD"', # Hermes
        'echo "PLANET: $PLANET"', # Jupiter
        'echo "ELEMENT: $ELEMENT"' # Fire
    ]
)
runner.register(show)
```

You can see the following output:

- `GOD: Hermes`. There is no `env` named `GOD`, and the only environment file defined `GOD` is `a.env`
- `PLANET: Jupiter`. There are two `env`s named `PLANET`. The latter overrides the first, and both override `env_file`s.
- `ELEMENT: Fire`. There is no `env` named `ELEMENT`. As for `env_file`s, `b.env` overrides `a.env`.

For more detailed visualization, please look at the following table:

| Environment | `env_files[0]` a.env | `env_files[1]` b.env | `envs[0]` | `envs[1]`   | Final   |
|-------------|----------------------|----------------------|-----------|-------------|---------|
| GOD         | **Hermes**           |                      |           |             | Hermes  |
| PLANET      | Mercury              | Mars                 | Venus     | **Jupiter** | Jupiter |
| ELEMENT     | Air                  | **Fire**             |           |             | Fire    |

# Next

Next, you can learn about inter-task communication using [`xcom`](xcom.md).

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
