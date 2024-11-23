from zrb.builtin.git import git_commit
from zrb.builtin.group import git_subtree_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.git_subtree import add_subtree, pull_all_subtrees, push_all_subtrees


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
    pull_all_subtrees()


@make_task(
    name="git-push-subtree",
    description="📤 Push subtree",
    upstream=git_commit,
    group=git_subtree_group,
    alias="push",
)
def git_push_subtree(ctx: AnyContext):
    push_all_subtrees()
