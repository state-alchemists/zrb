from zrb.builtin.git import git_commit
from zrb.builtin.group import git_subtree_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.git_subtree import add_subtree, load_config, pull_subtree, push_subtree


@make_task(
    name="git-add-subtree",
    input=[
        StrInput(
            name="name", description="Subtree config name", prompt="Subtree config name"
        ),
        StrInput(
            name="repo-url", description="Subtree repo URL", prompt="Subtree repo URL"
        ),
        StrInput(
            name="repo-branch",
            description="Subtree repo branch",
            prompt="Subtree repo branch",
        ),
        StrInput(
            name="repo-prefix",
            description="Subtree repo prefix",
            prompt="Subtree repo prefix",
        ),
    ],
    description="➕ Add subtree",
    upstream=git_commit,
    group=git_subtree_group,
    alias="add",
)
def git_add_subtree(ctx: AnyContext):
    add_subtree(
        name=ctx.input.name,
        repo_url=ctx.input["repo-url"],
        branch=ctx.input["repo-branch"],
        prefix=ctx.input["repo-prefix"],
    )


@make_task(
    name="git-pull-subtree",
    description="📥 Pull subtree",
    upstream=git_commit,
    group=git_subtree_group,
    alias="pull",
)
def git_pull_subtree(ctx: AnyContext):
    config = load_config()
    if not config.data:
        raise ValueError("No subtree config found")
    first_err: Exception | None = None
    for name, detail in config.data.items():
        try:
            ctx.print(f"Pull from subtree {name}")
            pull_subtree(detail.prefix, detail.repo_url, detail.branch)
        except Exception as e:
            if first_err is None:
                first_err = e
            ctx.log_error(e)
    if first_err is not None:
        raise first_err


@make_task(
    name="git-push-subtree",
    description="📤 Push subtree",
    upstream=git_commit,
    group=git_subtree_group,
    alias="push",
)
def git_push_subtree(ctx: AnyContext):
    config = load_config()
    if not config.data:
        raise ValueError("No subtree config found")
    first_err: Exception | None = None
    for name, detail in config.data.items():
        try:
            ctx.print(f"Push to subtree {name}")
            push_subtree(detail.prefix, detail.repo_url, detail.branch)
        except Exception as e:
            if first_err is None:
                first_err = e
            ctx.log_error(e)
    if first_err is not None:
        raise first_err
