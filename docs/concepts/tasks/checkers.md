🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# Checkers

Checkers are special type of tasks. You can use checkers to check for other task's readiness.

Currently there are three types of checkers:
- PathChecker
- PortChecker
- HttpChecker


Let's say you invoke `npm run build:watch`. This command will build your Node.js App into `dist` directory, as well as watch the changes and rebuild your app as soon as there are some changes.

- A web server is considered ready if it's HTTP Port is accessible. You can use `HTTPChecker` to check for web server readiness.
- But, before running the web server to start, you need to build the frontend and make sure that the `src/frontend/dist` has been created. You can use `PathChecker` to check for frontend readiness.

Let's see how we can do this:

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

> Aside from `PathChecker` and `HTTPChecker`, you can also use `PortChecker` to check for TCP port readiness.

You can then run the server by invoking:

```bash
zrb run-server
```


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)