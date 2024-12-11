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
async def get_git_diff(ctx: AnyContext):
    repo_dir = await get_repo_dir(log_method=ctx.print)
    diff = await get_diff(
        repo_dir, ctx.input.source, ctx.input.current, log_method=ctx.print
    )
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
async def prune_local_branches(ctx: AnyContext):
    repo_dir = await get_repo_dir(log_method=ctx.print)
    branches = await get_branches(repo_dir, log_method=ctx.print)
    current_branch = await get_current_branch(repo_dir, log_method=ctx.print)
    for branch in branches:
        if branch == current_branch or branch == "main" or branch == "master":
            continue
        ctx.print(stylize_yellow(f"Removing local branch: {branch}"))
        try:
            await delete_branch(repo_dir, branch, log_method=ctx.print)
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
async def git_commit(ctx: AnyContext):
    repo_dir = await get_repo_dir(log_method=ctx.print)
    ctx.print("Add changes to staging")
    await add(repo_dir, log_method=ctx.print)
    ctx.print("Commit changes")
    await commit(repo_dir, ctx.input.message, log_method=ctx.print)


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
async def git_pull(ctx: AnyContext):
    repo_dir = await get_repo_dir(log_method=ctx.print)
    remote = ctx.input.remote
    current_branch = await get_current_branch(repo_dir, log_method=ctx.print)
    ctx.print(f"Pulling from {remote}/{current_branch}")
    await pull(repo_dir, remote, current_branch, log_method=ctx.print)


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
async def git_push(ctx: AnyContext):
    repo_dir = await get_repo_dir(log_method=ctx.print)
    remote = ctx.input.remote
    current_branch = await get_current_branch(repo_dir, log_method=ctx.print)
    ctx.print(f"Pushing to {remote}/{current_branch}")
    await push(repo_dir, remote, current_branch, log_method=ctx.print)
