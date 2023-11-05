🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RSyncTask

```python
from zrb import (
    runner, CmdTask, RSyncTask, RemoteConfig, PasswordInput, StrInput
)

upload = RSyncTask(
    name='upload',
    inputs=[
        PasswordInput(name='passsword'),
        StrInput(name='src'),
        StrInput(name='dst'),
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    is_remote_src=False,
    is_remote_dst=True
    src='{{input.src}}',
    dst='{{input.dst}}',
)
runner.register(upload)

download = RSyncTask(
    name='download',
    inputs=[
        PasswordInput(name='passsword'),
        StrInput(name='src'),
        StrInput(name='dst'),
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    is_remote_src=True,
    is_remote_dst=False
    src='{{input.src}}',
    dst='{{input.dst}}',
)
runner.register(download)
```

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
