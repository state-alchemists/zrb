from zrb.builtin.monorepo._config import MONOREPO_CONFIG
from zrb.builtin.monorepo._group import monorepo_group
from zrb.builtin.monorepo._helper import (
    create_add_subrepo_task,
    create_pull_monorepo_task,
    create_pull_subrepo_task,
    create_push_monorepo_task,
    create_push_subrepo_task,
)
from zrb.helper.util import to_kebab_case
from zrb.runner import runner
from zrb.task.flow_task import FlowTask
from zrb.task_group.group import Group

_pull_monorepo = create_pull_monorepo_task()

PULL_SUBREPO_UPSTREAM = _pull_monorepo
PUSH_SUBREPO_UPSTREAM = _pull_monorepo
for name, config in MONOREPO_CONFIG.items():
    kebab_name = to_kebab_case(name)
    group = Group(
        name=kebab_name, parent=monorepo_group, description=f"Subrepo {name} management"
    )
    origin = config.get("origin", "")
    folder = config.get("folder", "")
    branch = config.get("branch", "main")

    pull_subrepo = FlowTask(
        name="pull",
        group=group,
        upstreams=[_pull_monorepo],
        steps=[
            create_add_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"add-{kebab_name}-subrepo",
            ),
            create_pull_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"pull-{kebab_name}-subrepo",
            ),
        ],
    )
    runner.register(pull_subrepo)

    linked_pull_subrepo = FlowTask(
        name=f"pull-{kebab_name}",
        upstreams=[PULL_SUBREPO_UPSTREAM],
        steps=[
            create_add_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"add-{kebab_name}-subrepo",
            ),
            create_pull_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"pull-{kebab_name}-subrepo",
            ),
        ],
    )
    PULL_SUBREPO_UPSTREAM = linked_pull_subrepo

    push_subrepo = FlowTask(
        name="push",
        group=group,
        upstreams=[_pull_monorepo],
        steps=[
            create_add_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"add-{kebab_name}-subrepo",
            ),
            create_pull_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"pull-{kebab_name}-subrepo",
            ),
            create_push_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"push-{kebab_name}-subrepo",
            ),
            create_push_monorepo_task(task_name="push-monorepo"),
        ],
    )
    runner.register(push_subrepo)

    linked_push_subrepo = FlowTask(
        name=f"push-{kebab_name}",
        upstreams=[PUSH_SUBREPO_UPSTREAM],
        steps=[
            create_add_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"add-{kebab_name}-subrepo",
            ),
            create_pull_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"pull-{kebab_name}-subrepo",
            ),
            create_push_subrepo_task(
                origin=origin,
                folder=folder,
                branch=branch,
                task_name=f"push-{kebab_name}-subrepo",
            ),
        ],
    )
    PUSH_SUBREPO_UPSTREAM = linked_push_subrepo


_push_monorepo = create_push_monorepo_task(task_name="push-monorepo")
PUSH_SUBREPO_UPSTREAM >> _push_monorepo
PUSH_SUBREPO_UPSTREAM = _push_monorepo
