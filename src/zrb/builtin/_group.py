from ..task_group.group import Group

show = Group(
    name='show', description='Show things (usually visual matter only)'
)
show_principle = Group(
    name='principle',
    parent=show,
    description='Show principle'
)
get = Group(
    name='get', description='Return things into stdout'
)
create = Group(
    name='create', description='Create things'
)
update = Group(
    name='update', description='Update things'
)
install = Group(
    name='install', description='Install things'
)
install_ubuntu = Group(
    name='ubuntu',
    parent=install,
    description='Install things on ubuntu'
)
start = Group(
    name='start', description='Starting long running processes'
)
