🔖 [Home](../../README.md)

# Zrb Documentation

Welcome to the official documentation for Zrb, your automation powerhouse!

Zrb is a powerful and flexible tool designed to help you automate repetitive tasks, integrate with modern technologies like Large Language Models (LLMs), and build custom workflows using Python. Whether you are a beginner looking to automate simple scripts or an experienced developer building complex CI/CD pipelines, Zrb provides the tools and structure you need.

This documentation is your starting point to learn more about Zrb, understand its core concepts, and explore its capabilities.

## Basic Principles

When working with Zrb, there are some common principles you should have in mind.

* **Everything defined in `zrb_init.py`.**
    * You can place `zrb_init.py` anywhere.
    * You can define tasks, groups, and configurations in your `zrb_init.py`
    * Any tasks and configurations defined in `<dir>/zrb_init.py` will works on the `<dir>` as well as its sub-directories. 

    ```mermaid
    flowchart LR
    subgraph homeDir ["/a (Can Access A)"]
        homeDirZrbInit["/a/zrb_init.py<br/>(Define A)"]
        subgraph projectDir ["/a/b (Can access A and B)"]
            projectDirZrbInit["/a/b/zrb_init.py<br />(Define B)"]
            subgraph subProjectDir ["/a/b/c (Can access A, B and C)"]
                subProjectDirZrbInit["/a/b/c/zrb_init.py<br />(Define C)"]
            end
        end
        subgraph otherProjectDir ["/a/d (Can access A and D)"]
            otherProjectDirZrbInit["zrb_init.py<br />(Define D)"]
        end
    end
    ```
* **Task access hierarchy always started with a `cli`**

  You can add `groups` or `tasks` to the `cli`.
  
  You can also add `groups` inside existing `groups`.
  
  But you have to make sure that everything started with a `cli`. Otherwise, your `tasks` or `groups` won't be accessible.

  ```python
  from zrb import cli, Group, CmdTask
  
  # make and register "hello", task to the cli. 
  cli.add_task(CmdTask(name="hello", cmd="echo hello"))

  # make and register "alarm" group to the cli.
  alarm_group = cli.add_group(Group(name="alarm"))
  # make and register "wake-up" task to the "alarm" group.
  alarm_group.add_task(CmdTask(name="wake-up", cmd="echo wake up!"))

  # make and register "critical" group to the "alarm" group.
  alarm_critical_group = alarm_group.add_group(Group(name="critical"))
  # make and register "fire" task to the "critical" group.
  alarm_critical_group.add_task(CmdTask(name="fire", cmd="echo fire!!!"))
  ```
  
  The mental model hierarchy will be:

  ```
  cli
    [task] hello          zrb hello
    [group] alarm
      [task] wake-up      zrb alarm wake-up
      [group] critical
        [task] fire       zrb alarm critical fire
  ```

* **You can use `upstreams` parameter or `>>` operator to define task dependencies.**
  
  Whenever Zrb run a `task`, it will first check for all its upstreams to be completed.
  
  As each Task can have their own `retries` strategy, having a multiple task with dependencies to each others makes a more efficient retry attempts.

  ```python
  from zrb import cli, CmdTask

  become_novice = CmdTask(name="become-novice", cmd="echo become novice")
  become_merchant = CmdTask(
    name="become-merchant",
    cmd="echo become merchant",
    upstream=become_novice,  # To be a merchant, you should be a novice first.
  )
  become_alchemist = cli.add_task(
    CmdTask(
      name="become-alchemist",
      cmd="echo become alchemist",
      upstream=become_merchant,  # To be an achemist, you should be a merchant first.
    )
  )
  ```

  or

  ```python
  from zrb import cli, CmdTask

  become_novice = CmdTask(name="become-novice", cmd="echo become novice")
  become_merchant = CmdTask(name="become-merchant", cmd="echo become merchant")
  become_alchemist = cli.add_task(CmdTask(name="become-alchemist", cmd="echo become alchemist"))

  become_novice >> become_merchant >> become_alchemist
  ```
  
  As `become_alchemist` depends on `become_merchant`, and `become_merchant` depends on `become_novice`, you can see the tasks will always run in sequence whenever you invoke the `become-alchemist` task.

  ```sh
  zrb become-alchemist
  ```

  ```
  become novice
  become merchant
  become alchemist
  ```

* **Use `task`'s `input` to get user inputs.**

  You can access `input` by using `ctx.input` property.
  
  ```python
  from zrb import cli, CmdTask, StrInput

  cli.add_task(
    CmdTask(
      name="hello",
      input=[
        StrInput(name="name"),
        StrInput(name="prefix"),
      ],
      cmd="echo Hello {ctx.input.prefix} {ctx.input.name}",
    )
  )
  ```

  You can run the task while providing the inputs, or you can trigger the interactive session.

  ```sh
  zrb hello --name Edward --prefix Mr
  # or
  zrb hello
  ```

  ```
  Hello Mr Edward
  ```

* **Use `task`'s `env` to get environment variable values.**

  You can access `env` by using `ctx.env` property.
 
  ```python
  from zrb import cli, CmdTask, Env

  cli.add_task(
    CmdTask(
      name="hello",
      env=[
        Env(name="USER", default="nobody"),
        Env(name="SHELL", default="sh"),
      ],
      cmd="echo Hello {ctx.env.USER}, your shell is {ctx.env.sh}",
    )
  )
  ```

  You can invoke the task as follows

  ```sh
  zrb hello
  ```

  ```
  Hello gofrendi, your shell is zsh
  ```

* **Use `xcom` to for inter `task` communication.**

  You can think of `xcom` as dictionary of [`deque`](https://docs.python.org/3/library/collections.html#collections.deque). You can manually create key and push value to it or pop its value.

  Zrb automatically push task's return value to the `xcom`.

  You can access `xcom` by using `ctx.xcom`.

  ```python
  from zrb import cli, CmdTask

  create_magic_number = CmdTask(name="create-magic-number", cmd="echo 42")
  cli.add_task(
    CmdTask(
      name="show-magic-number",
      upstream=create_magic_number,
      cmd="echo {ctx.xcom['create-magic-number'].pop()}",
    )
  )
  ```

* **Use `@make_task` decorator for more complex usecase.**

  ```python
  from zrb import cli, make_task, AnyContext, StrInput


  @make_task(
    name="count-word",
    input=StrInput(name="text"),
    group=cli,
  )
  def count_word(ctx: AnyContext) -> int:
    text = ctx.input.text
    words = text.split(" ")
    return len(words)
  ```

  You can invoke the task.

  ```sh
  zrb count-word --text "the quick brown fox jumps over the lazy dog"
  ```

  ```
  9
  ```


# Topics

* [Installation and Configuration](./installation-and-configuration/README.md)
    * [Configuration](./installation-and-configuration/configuration/README.md)
* [Core Concepts](./core-concepts/README.md)
    * [CLI and Group](./core-concepts/cli-and-group.md)
    * [Task](./core-concepts/task/README.md)
    * [Input](./core-concepts/input/README.md)
    * [Env](./core-concepts/env/README.md)
    * [Session and Context](./core-concepts/session-and-context/README.md)
        * [Session](./core-concepts/session-and-context/session.md)
        * [Context](./core-concepts/session-and-context/context.md)
        * [XCom](./core-concepts/session-and-context/xcom.md)
*   [Advanced Topics](#advanced-topics)
    * [CI/CD Integration](./ci_cd.md)
    * [Upgrading Guide 0.x.x to 1.x.x](./upgrading_guide_0_to_1.md)
    * [Troubleshooting](./troubleshooting/)
    * [Maintainer Guide](./maintainer-guide.md)
    * [Changelog](./changelog.md)
    * [Creating a Custom Zrb Powered CLI](./creating-custom-zrb-powered-cli.md)

🔖 [Home](../../README.md)
