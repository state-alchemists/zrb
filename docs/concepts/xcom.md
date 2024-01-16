🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# XCom

Occasionally, you need your Tasks to pass data to each other. You can do this by using the XCom mechanism.

The Xcom mechanism is highly dependent on Task Execution ID. In short, a Task and all its upstreams/downstreams share the same Execution ID.

## Execution ID

<div align="center">
  <img src="../_images/emoji/ticket.png"/>
  <p>
    <sub>
      Sharing a ticket is like sharing a dessert; everyone's happy until it's their turn to pay.
    </sub>
  </p>
</div>

In Zrb, every Task and all its upstreams will share the same Execution ID. 
To get the Execution ID, you can use the `get_execution_id()` method or `$_ZRB_EXECUTION_ID`, depending on your situation.

Let's see the following example:

```python
from zrb import runner, Parallel, CmdTask, Task, python_task

hello_cmd = CmdTask(
    name='hello-cmd',
    cmd='echo "Execution ID: $_ZRB_EXECUTION_ID"'
)

@python_task(
    name='hello-py'
)
def hello_py(*args, **kwargs):
    task = kwargs.get('_task')
    return f'Execution ID: {task.get_execution_id()}'

hello = Task(
    name='hello',
    run=lambda *args, **kwargs: kwargs.get('_task').get_execution_id()
)

Parallel(hello_cmd, hello_py) >> hello
runner.register(hello)
```

You will find that `hello-cmd`, `hello-py`, and `hello` share the same Execution ID.

You can use ExecutionID for many cases. Zrb internally uses the Execution ID for Cross Task Communication (XCom).

## XCom (Cross Task Communication)

<div align="center">
  <img src="../_images/emoji/telephone_receiver.png"/>
  <p>
    <sub>
      Remember when phones were dumb and people were smart? Good times.
    </sub>
  </p>
</div>

You can think of XCom as a global dictionary shared by all Tasks during the execution.

The structure of `xcom` dictionary is as follows:

```python
__xcom: Mapping[str, Mapping[str, str]] = {
    'execution-id-1': {
        'key-1': 'value-1',
        'key-2': 'value-2'
    },
    'execution-id-2': {
        'key-1': 'value-1',
        'key-2': 'value-2'
    }
}
```

To set and get value from XCom, you can use `set_xcom` and `get_xcom` method. Zrb automatically puts Tasks's return value into the XCom dictionary.

```python
from zrb import runner, Parallel, CmdTask, python_task, Task

hello_cmd = CmdTask(
    name='hello-cmd',
    cmd='echo hello-cmd'
)

@python_task(
    name='hello-py'
)
def hello_py(*args, **kwargs):
    task: Task = kwargs.get('_task')
    task.set_xcom('my-xcom', 'my-value')
    return 'hello-py'

hello = CmdTask(
    name='hello',
    cmd=[
        'echo {{task.get_xcom("hello-cmd")}}', # hello-cmd
        'echo {{task.get_xcom("hello-py")}}',  # hello-py
        'echo {{task.get_xcom("my-xcom")}}',   # my-value
    ],
)

Parallel(hello_cmd, hello_py) >> hello
runner.register(hello)
```

Zrb automatically handles the `execution-id` part of your XCom dictionary so that you can focus on the XCom key and value.

Furthermore, Zrb automatically put the return value of your Task into the XCom dictionary.


🔖 [Table of Contents](../README.md) / [Concepts](README.md)
