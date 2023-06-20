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

# DockerComposeTask parameters

Every [task parameters](./task.md#common-task-parameters) are applicable here. Additionally, a `DockerComposeTask` has it's own specific parameters.

## `executable`

## `compose_service_configs`

## `compose_file`

## `compose_cmd`

## `compose_options`

## `compose_flags`

## `compose_args`

## `compose_env_prefix`

## `setup_cmd`

## `setup_cmd_path`

## `cwd`

## `max_output_line`

## `max_error_line`

## `preexec_fn`


# DockerComposeTask methods

Please refer to [common task methods](./README.md#common-task-methods).


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)