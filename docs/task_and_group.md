# Task and Group

## Usage

Tasks and groups are defined in Python code (typically in a `zrb_init.py` file). The Zrb runner will then execute the tasks and groups in the order specified by their dependencies. Tasks can be added to groups using the `add_task` method, and subgroups can be added to groups using the `add_group` method. Dependencies between tasks can be defined using the `>>` operator (e.g., `task1 >> task2` means that `task2` depends on `task1`). The `cli` object is used to register tasks and groups with the command-line interface, allowing them to be executed from the command line.