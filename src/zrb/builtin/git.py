from zrb.builtin.group import git_branch_group, git_group
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.cli.style import stylize_green, stylize_red, stylize_yellow
from zrb.util.git import (
    add,
    commit,
    delete_branch,
    get_branches,
    get_current_branch,
    get_diff,
    get_repo_dir,
    pull,
    push,
)


@make_task(
    name="get-git-diff",
    input=[
        StrInput(
            name="source",
            description="Source branch/tag/commit",
            prompt="Source branch/tag/commit",
            default_str="main",
        ),
        StrInput(
            name="current",
            description="Current branch/tag/commit",
            prompt="Current branch/tag/commit",
            default_str="HEAD",
        ),
        BoolInput(
            name="created",
            description="Include created files",
            prompt="Include created files",
            default_str="True",
        ),
        BoolInput(
            name="removed",
            description="Include removed files",
            prompt="Include removed files",
            default_str="True",
        ),
        BoolInput(
            name="updated",
            description="Include updated files",
            prompt="Include updated files",
            default_str="True",
        ),
    ],
    description="🔍 Get modified files",
    group=git_group,
    alias="diff",
)
def get_git_diff(ctx: AnyContext):
    repo_dir = get_repo_dir()
    diff = get_diff(repo_dir, ctx.input.source, ctx.input.current)
    result = []
    decorated = []
    if ctx.input.created and diff.created:
        decorated += [stylize_green(f"++ {name}") for name in diff.created]
        result += diff.created
    if ctx.input.updated and diff.updated:
        decorated += [stylize_yellow(f"+- {name}") for name in diff.updated]
        result += diff.updated
    if ctx.input.removed and diff.removed:
        decorated += [stylize_red(f"-- {name}") for name in diff.removed]
        result += diff.removed
    if len(decorated) > 0:
        decorated = [""] + decorated + [""]
    ctx.print(
        "\n" + "\n".join((f"    {decorated_line}" for decorated_line in decorated))
    )
    return "\n".join(result)


@make_task(
    name="prune-local-git-branches",
    description="🧹 Prune local branches",
    group=git_branch_group,
    alias="prune",
)
def prune_local_branches(ctx: AnyContext):
    repo_dir = get_repo_dir()
    branches = get_branches(repo_dir)
    current_branch = get_current_branch(repo_dir)
    for branch in branches:
        if branch == current_branch or branch == "main" or branch == "master":
            continue
        ctx.print(stylize_yellow(f"Removing local branch: {branch}"))
        try:
            delete_branch(repo_dir, branch)
        except Exception as e:
            ctx.log_error(e)


@make_task(
    name="git-commit",
    input=StrInput(
        name="message",
        description="Commit message",
        prompt="Commit message",
        default_str="Add feature/fix bug",
    ),
    description="📝 Commit changes",
    group=git_group,
    alias="commit",
)
def git_commit(ctx: AnyContext):
    repo_dir = get_repo_dir()
    ctx.print("Add changes to staging")
    add(repo_dir)
    ctx.print("Commit changes")
    commit(repo_dir, ctx.input.message)


@make_task(
    name="git-pull",
    description="📥 Pull changes from remote repository",
    input=StrInput(
        name="remote",
        description="Remote name",
        prompt="Remote name",
        default_str="origin",
    ),
    upstream=git_commit,
    group=git_group,
    alias="pull",
)
def git_pull(ctx: AnyContext):
    repo_dir = get_repo_dir()
    remote = ctx.input.remote
    current_branch = get_current_branch(repo_dir)
    ctx.print(f"Pulling from {remote}/{current_branch}")
    pull(repo_dir, remote, current_branch)


@make_task(
    name="git-push",
    description="📤 Push changes to remote repository",
    input=StrInput(
        name="remote",
        description="Remote name",
        prompt="Remote name",
        default_str="origin",
    ),
    upstream=git_commit,
    group=git_group,
    alias="push",
)
def git_push(ctx: AnyContext):
    repo_dir = get_repo_dir()
    remote = ctx.input.remote
    current_branch = get_current_branch(repo_dir)
    ctx.print(f"Pushing to {remote}/{current_branch}")
    push(repo_dir, remote, current_branch)
