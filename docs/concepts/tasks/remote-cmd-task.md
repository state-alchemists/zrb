🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RemoteCmdTask

```python
from zrb import (
    runner, CmdTask, RemoteCmdTask, RemoteConfig, PasswordInput
)

install_curl = RemoteCmdTask(
    name='install-curl',
    inputs=[
        PasswordInput(name='passsword')
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    cmd=[
        'sudo apt update',
        'sudo apt install curl --y'
    ]
)
runner.register(install_curl)
```

RemoteCmdTask exposes several environments that you can use on your `cmd` and `cmd_path`

- `_CONFIG_HOST`
- `_CONFIG_PORT`
- `_CONFIG_SSH_KEY`
- `_CONFIG_USER`
- `_CONFIG_PASSWORD`
- `_CONFIG_MAP_<UPPER_SNAKE_CASE_NAME>`

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
