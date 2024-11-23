from zrb.builtin.group import git_group
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.cli.style import (
    stylize_green,
    stylize_red,
    stylize_section_header,
    stylize_yellow,
)
from zrb.util.git import get_diff


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
    diff = get_diff(ctx.input.source, ctx.input.current)
    result = []
    decorated = []
    if ctx.input.created:
        decorated.append(stylize_section_header("Created"))
        decorated += [stylize_green(f"++{name}") for name in diff.created]
        result += diff.created
    if ctx.input.updated:
        decorated.append(stylize_section_header("Updated"))
        decorated += [stylize_yellow(f"+-{name}") for name in diff.updated]
        result += diff.updated
    if ctx.input.removed:
        decorated.append(stylize_section_header("Removed"))
        decorated += [stylize_red(f"--{name}") for name in diff.removed]
        result += diff.removed
    ctx.print("\n" + "\n".join((f"  {decorated_line}" for decorated_line in decorated)))
    return "\n".join(result)
