
🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# FlowTask

FlowTask allows you to compose several actions into a single tasks.

```python
from zrb import FlowTask, FlowNode

prepare_app = FlowTask(
    name='prepare-app',
    nodes=[
        # prepare backend and frontend concurrently
        [
            FlowNode(
                name='prepare-backend',
                cmd=[
                    'cd frontend',
                    'npm run build'
                ]
            ),
            FlowNode(
                name='prepare-frontend',
                cmd='pip install -r requirements.txt'
            )
        ],
        # show-instruction will run once backend and frontend are prepared
        FlowNode(
            name='show-instruction',
            cmd='echo "App is ready, start it!!!"'
        )
    ]
)
runner.register(prepare_app)
```

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)