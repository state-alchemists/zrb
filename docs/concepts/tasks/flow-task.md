
🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# FlowTask

FlowTask allows you to compose several unrelated tasks/actions into a single tasks.

```python
from zrb import FlowTask, FlowNode, CmdTask, HttpChecker, runner
import os

current_dir = os.dirname(__file__)

prepare_backend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(current_dir, 'app', 'backend'),
    cmd='pip install -r requirements.txt'
)

prepare_frontend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(current_dir, 'app', 'frontend'),
    cmd='npm install && npm run build'
)

start_app = CmdTask(
    name='start-app',
    cwd=os.path.join(current_dir, 'app', 'backend'),
    cmd='uvicorn main:app --port 8080',
    checkers=[
        HttpChecker(port=8080)
    ]
)

prepare_and_start_app = FlowTask(
    name='prepare-and-start-app',
    nodes=[
        # Prepare backend and frontend concurrently
        [
            FlowNode(task=prepare_backend),
            FlowNode(task=prepare_frontend)
        ],
        # Then start app
        FlowNode(task=start_app),
        # And finally show instruction
        FlowNode(
            name='show-instruction',
            cmd='echo "App is ready, Check your browser"'
        )
    ]
)
runner.register(prepare_app)
```

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)