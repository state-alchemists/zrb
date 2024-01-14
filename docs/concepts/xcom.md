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

In Zrb, a Task and all its upstreams will share the same Execution ID. 
To get the Execution ID, you can use the `get_execution_id` method or `$_ZRB_EXECUTION_ID`, depending on whether you use a TaskClass or `@python_task` decorator.

Let's see how we can get the Execution ID on different tasks:

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
    task.print_out(f'Execution ID: {task.get_execution_id()}')

hello = Task(
    name='hello',
    run=lambda *args, **kwargs: kwargs.get('_task').get_execution_id()
)

Parallel(hello_cmd, hello_py) >> hello
runner.register(hello)
```

You will find that `hello-cmd`, `hello-py`, and `hello` share the same Execution ID.

You can use ExecutionID for many cases, especially those related to Cross Task Communication (XCom).

## XCom (Cross Task Communication)

<div align="center">
  <img src="../_images/emoji/telephone_receiver.png"/>
  <p>
    <sub>
      Remember when phones were dumb and people were smart? Good times.
    </sub>
  </p>
</div>

All instances of BaseTask share a global `xcom` dictionary. You can think of `xcom` as in-memory key-value storage.

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

To set and get value from `xcom`, you can use `set_xcom` and `get_xcom` method. Zrb automatically handle `execution-id` so that you can focus on xcom's key and value.

Let's see the following example:

```python
from zrb import runner, Parallel, CmdTask, python_task, Task

set_xcom_cmd = CmdTask(
    name='set-xcom-cmd',
    cmd='echo "hi{{task.set_xcom("one", "ichi")}}"'
)

@python_task(
    name='set-xcom-py'
)
def set_xcom_py(*args, **kwargs):
    task: Task = kwargs.get('_task')
    task.set_xcom('two', 'ni')


get_xcom_cmd = CmdTask(
    name='get-xcom-cmd',
    cmd=[
        'echo {{task.get_xcom("one")}}',
        'echo {{task.get_xcom("two")}}',
    ]
)

@python_task(
    name='get-xcom-py'
)
def get_xcom_py(*args, **kwargs):
    task: Task = kwargs.get('_task')
    task.print_out(task.get_xcom("one"))
    task.print_out(task.get_xcom("two"))


test_xcom = Task(name='test-xcom')
Parallel(set_xcom_cmd, set_xcom_py) >> Parallel(get_xcom_cmd, get_xcom_py) >> test_xcom
runner.register(test_xcom)
```

The example shows that `set-xcom-cmd` and `set-xcom-py` set XCom values `one` and `two`, respectively.

On the other hand, `get-xcom-cmd` and `get-xcom-py` fetch the values and print them.

Furthermore, every Zrb Task has its return values saved as `__xcom['execution-id']['task-name']`. To have a better understanding, let's see the following example:

```python
from zrb import runner, Parallel, CmdTask, python_task

hello_cmd = CmdTask(
    name='hello-cmd',
    cmd='echo hello-cmd',
)

@python_task(
    name='hello-py'
)
def hello_py(*args, **kwargs):
    return 'hello-py'

hello = CmdTask(
    name='hello',
    cmd=[
        'echo {{task.get_xcom("hello-cmd")}}',
        'echo {{task.get_xcom("hello-py")}}',
    ],
)

Parallel(hello_cmd, hello_py) >> hello
runner.register(hello)
```

With XCom, you can easily share your data across your tasks.



🔖 [Table of Contents](../README.md) / [Concepts](README.md)
