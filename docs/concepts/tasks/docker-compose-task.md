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

# DockerComposeTask Parameters

Every [task parameters](./task.md#common-task-parameters) are applicable here. Additionally, a `DockerComposeTask` has it's own specific parameters.

## `executable`

Executable to run `compose_cmd` and `setup_cmd` command.

- __Required:__ False
- __Possible values:__ String representing the terminal, for example `bash` or `zsh`.
- __Default value:__ Equals to `ZRB_SHELL` If set. Otherwise it will be `bash`.

## `compose_service_configs`

Env and EnFile configuration for each services in your `compose_file`.

For example, you want to set postgre's servie `POSTGRES_USER` into `root`. In that case, you can do:

```python
from zrb import runner, DockerComposeTask, ServiceConfig, Env
start_container = DockerComposeTask(
    name='start-container',
    compose_cmd='up',
    compose_file='docker-compose.yml',
    compose_service_configs={
      'postgres': ServiceConfig(
        envs=[
          Env(name='POSTGRES_USER', default='root')
        ]
      )
    }
)
runner.register(start_container)
```

- __Required:__ False
- __Possible values:__ Map of `ServiceConfig`.
- __Default value:__ Empty map.

## `compose_file`

Your docker-compose file path.

If not set, Zrb will try to find the following files in your `cwd`:

- `compose.yml`
- `compose.yaml`
- `docker-compose.yml`
- `docker-compose.yaml`

Zrb will throws error if no `compose_file` found.

- __Required:__ False
- __Possible values:__ String representing the docker compose file or `None`.
- __Default value:__ `None`


## `compose_cmd`

Docker compose command (i.e: `docker compose <compose-cmd>`)

- __Required:__ False
- __Possible values:__ String representing the docker compose command.
- __Default value:__ `up`

## `compose_options`

Docker compose options. Type `docker compose --help` to see possible options.

Example:


```python
from zrb import runner, DockerComposeTask, ServiceConfig, Env
start_container = DockerComposeTask(
    name='start-container',
    compose_cmd='up',
    compose_file='docker-compose.yml',
    compose_options={
      '--project-name': 'my-project',
      '--parallel': 5
    }
)
runner.register(start_container)
```

- __Required:__ False
- __Possible values:__ Map of compose option.
- __Default value:__ Empty map.


## `compose_flags`

## `compose_args`

## `compose_env_prefix`

## `setup_cmd`

## `setup_cmd_path`

## `cwd`

## `max_output_line`

## `max_error_line`

## `preexec_fn`


# DockerComposeTask Methods

Please refer to [common task methods](./README.md#common-task-methods).


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)