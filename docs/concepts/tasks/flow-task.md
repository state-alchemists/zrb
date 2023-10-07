
🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# FlowTask

FlowTask allows you to compose several unrelated tasks/actions into a single tasks.

```python
from zrb import FlowTask, CmdTask, HttpChecker, runner
import os

CURRENT_DIR = os.dirname(__file__)

prepare_backend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(CURRENT_DIR, 'app', 'backend'),
    cmd='pip install -r requirements.txt'
)

prepare_frontend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(CURRENT_DIR, 'app', 'frontend'),
    cmd='npm install && npm run build'
)

start_app = CmdTask(
    name='start-app',
    cwd=os.path.join(CURRENT_DIR, 'app', 'backend'),
    cmd='uvicorn main:app --port 8080',
    checkers=[
        HttpChecker(port=8080)
    ]
)

prepare_and_start_app = FlowTask(
    name='prepare-and-start-app',
    steps=[
        # Prepare backend and frontend concurrently
        [
            prepare_backend,
            prepare_frontend
        ],
        # Then start app
        start_app,
        # And finally show instruction
        CmdTask(
            name='show-instruction',
            cmd='echo "App is ready, Check your browser"'
        )
    ]
)
runner.register(prepare_app)
```

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)