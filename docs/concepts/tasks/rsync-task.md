🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RsyncTask

```python
from zrb import (
    runner, CmdTask, RsyncTask, RemoteConfig, PasswordInput, StrInput
)

upload = RsyncTask(
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
            password='{{input.password}}',
            config_map={
                'dir': '192-168-1-10'
            }
        )
    ],
    is_remote_src=False,
    src='$_CONFIG_MAP_DIR/{{input.src}}',
    is_remote_dst=True,
    dst='{{input.dst}}',
)
runner.register(upload)

download = RsyncTask(
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
    src='{{input.src}}',
    is_remote_dst=False,
    dst='$_CONFIG_MAP_DIR/{{input.dst}}',
)
runner.register(download)
```

RsyncTask exposes several environments that you can use on your `src` and `dst`

- `_CONFIG_HOST`
- `_CONFIG_PORT`
- `_CONFIG_SSH_KEY`
- `_CONFIG_USER`
- `_CONFIG_PASSWORD`
- `_CONFIG_MAP_<UPPER_SNAKE_CASE_NAME>`

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
