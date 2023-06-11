# Checkers

Some tasks might run forever, and you need a way to make sure whether those tasks are ready or not.

Let's say you invoke `npm run build:watch`. This command will build your Node.js App into `dist` directory, as well as watch the changes and rebuild your app as soon as there are some changes.

- You need to start the server after the app has been built for the first time.
- You can do this by checking whether the `dist` folder already exists or not.
- You can use `PathChecker` for this purpose

Let's see how to do this:

```python
from zrb import CmdTask, PathChecker, Env, EnvFile, runner

build_frontend = CmdTask(
    name='build-frontend',
    cmd='npm run build',
    cwd='src/frontend',
    checkers=[
        PathChecker(path='src/frontend/dist')
    ]
)

run_server = CmdTask(
    name='run-server',
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    env_files=[
        EnvFile(env_file='src/template.env', prefix='WEB')
    ]
    cmd='python main.py',
    cwd='src',
    upstreams=[
        build_frontend
    ],
    checkers=[HTTPChecker(port='{{env.PORT}}')],
)
runner.register(run_server)
```

Aside from `PathChecker`, Zrb also has `HTTPChecker` and `PortChecker`.