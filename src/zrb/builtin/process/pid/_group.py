from zrb.builtin.process._group import process_group
from zrb.task_group.group import Group

process_pid_group = Group(
    name="pid", parent=process_group, description="PID related commands"
)
