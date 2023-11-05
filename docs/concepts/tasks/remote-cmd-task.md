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

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
