🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Run Task by Schedule

Zrb doesn't have any built-in scheduler. However, there are some workarounds you can use:

- Creating an infinite loop
- Using Cronjob
- Using Airflow or other orchestrator

# Creating an Infinite Loop

The simplest approach is by turning your task into a function, and call your function after some interval.

For example, you want to run `hello` task every 5 seconds. Then you can create the following Python script and run it. 

```python
# file: scheduled_hello.py
from zrb import CmdTask, runner

import time

# You can import `hello` task from somewhere else
# e.g., from zrb_init import hello
hello = CmdTask(
    name='hello',
    cmd='echo "hello world"'
)
runner.register(hello)

while True:
    time.sleep(5)
    fn = hello.to_function()
    hello()
```

```bash
python scheduled_hello.py
```

# Using CronJob


A cron job is usually formatted as follow:

```
minute hour day month weekday <command-to-execute>
```

Suppose you want to run `zrb hello` every 5 seconds, you can edit your crontab by executing:

```bash
crontab -e
```

Crontab will ask you to choose a text editor. You can choose `nano` or anything you are familiar with.

Once you have choose your text editor, you can add the following line:

```
5 * * * * zrb hello >> .hello.log 2>&1
```

# Using Airflow or Other Orchestrator

If you are using Airflow, you can use a [BashOperator](https://airflow.apache.org/docs/apache-airflow/stable/howto/operator/bash.html) as follow:

```python
from airflow.decorators import dag
from airflow.operators.bash import BashOperator
from pendulum import datetime


@dag(start_date=datetime(2022, 8, 1), schedule='@daily', catchup=False)
def hello_dag():
    run_hello = BashOperator(
        task_id="run_hello",
        bash_command="zrb hello",
    )
```

For other orchestrators, please visit their respective document. As long as there is a way to run a python function or running a CLI command, you will be able to run Zrb Task



🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
