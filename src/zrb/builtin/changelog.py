import os
import re

from zrb.builtin.group import git_changelog_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.cli.style import stylize_green, stylize_muted, stylize_yellow
from zrb.util.cmd.command import run_command
from zrb.util.git import get_repo_dir

# Optional `v`/`v-` prefix, then major.minor.patch, then an optional
# rc/alpha/beta pre-release suffix. Matches v1.2.3, 1.2.3, v-1.2.3, 1.2.3-rc1...
_DEFAULT_PATTERN = r"^(v-?)?\d+\.\d+\.\d+([.-]?(rc|alpha|beta|a|b)\d*)?$"

_DEFAULT_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "changelog_template.md"
)

# Read-only git subcommands the LLM may run via the tool. Anything else
# (including `-c ...` config injection, which lands in args[0]) is refused.
_ALLOWED_GIT = {"diff", "log", "show", "shortlog", "tag"}

# SHA of git's permanent empty-tree object. Hard-coded in git's C source since
# 2008 (commit 346245a1bb by Jeff King); returned synthetically by
# find_cached_object() without ever being stored on disk. Valid in every repo.
# Reproduce with: git hash-object -t tree /dev/null
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@make_task(
    name="generate-changelog",
    input=[
        StrInput(
            name="dir",
            description="Changelog output directory",
            prompt="Changelog output directory",
            default="docs/changelog",
        ),
        StrInput(
            name="pattern",
            description="Tag pattern (regex)",
            prompt="Tag pattern (regex)",
            default=_DEFAULT_PATTERN,
        ),
        StrInput(
            name="sort",
            description="git tag --sort key",
            prompt="git tag --sort key",
            default="creatordate",
        ),
        StrInput(
            name="template",
            description="Changelog file template ({tag}, {previous_tag}, {date})",
            prompt="Changelog file template",
            default=_DEFAULT_TEMPLATE_PATH,
        ),
    ],
    description="📝 Generate one changelog file per matching git tag via LLM",
    group=git_changelog_group,
    alias="generate",
)
async def generate_changelog(ctx: AnyContext):
    repo_dir = await get_repo_dir(print_method=ctx.print)
    os.makedirs(ctx.input.dir, exist_ok=True)
    with open(ctx.input.template) as f:
        template = f.read()
    regex = re.compile(ctx.input.pattern)
    tags = await _matching_tags(ctx, repo_dir, ctx.input.sort, regex)
    if not tags:
        ctx.print(stylize_yellow("No tag matched the pattern"))
        return
    written = []
    for index, tag in enumerate(tags):
        out_path = os.path.join(ctx.input.dir, f"{tag}.md")
        if os.path.exists(out_path):
            ctx.print(stylize_muted(f"Skip {tag} (already exists)"))
            continue
        previous = tags[index - 1] if index > 0 else ""
        ctx.print(stylize_muted(f"Generating {tag} (since {previous or 'start'})"))
        content = await _summarize(ctx, repo_dir, template, tag, previous)
        with open(out_path, "w") as f:
            f.write(content)
        written.append(out_path)
        ctx.print(stylize_green(f"Wrote {out_path}"))
    return written


async def _matching_tags(ctx, repo_dir, sort, regex):
    result, code = await run_command(
        cmd=["git", "tag", f"--sort={sort}"],
        cwd=repo_dir,
        print_method=lambda *_: None,
    )
    if code != 0:
        raise Exception(f"git tag failed with exit code {code}")
    # splitlines(), not split("\n"): run_command yields CRLF, and a trailing
    # \r both breaks the `$`-anchored regex and produces "ambiguous argument"
    # if it leaks into a `tag..tag` range.
    return [t.strip() for t in result.output.splitlines() if regex.match(t.strip())]


async def _summarize(ctx, repo_dir, template, tag, previous):
    from zrb.llm.agent import create_agent  # lazy: pydantic_ai is a heavy extra

    log, stat, date = await _collect_log(ctx, repo_dir, tag, previous)
    # Pre-fill the values we already know; the LLM fills the section details.
    skeleton = (
        template.replace("{tag}", tag)
        .replace("{previous_tag}", previous or "(initial release)")
        .replace("{date}", date)
    )
    instruction = (
        f"Write the changelog for release {tag} "
        f"(previous release: {previous or 'none — this is the initial release'}).\n\n"
        f"Commit log:\n{log}\n\n"
        f"Change statistics (files changed, insertions, deletions):\n{stat}\n\n"
        f"Use the `git` tool to inspect individual file diffs only where the "
        f"commit log or stats above are unclear — always use --stat first to "
        f"identify relevant files, then fetch a specific file with "
        f'["diff", "{previous or _EMPTY_TREE}..{tag}", "--", "path/to/file"]. '
        f"Skip generated or lock files (poetry.lock, package-lock.json, "
        f"*.pb.go, auto-migrations) as they carry no changelog signal. "
        "Fill in the section details of this template, keeping "
        "its structure and headings; drop sections that have no entries:\n\n"
        f"{skeleton}\n\n"
        "Output only the resulting changelog markdown, nothing else."
    )
    agent = create_agent(tools=[_make_git_tool(ctx, repo_dir)], yolo=True)
    result = await agent.run(instruction)
    return result.output


async def _collect_log(ctx, repo_dir, tag, previous):
    log_rng = f"{previous}..{tag}" if previous else tag
    # `--` prevents "ambiguous argument" when a ref name resembles a path.
    log = await _git(
        ctx, repo_dir, ["log", "--no-merges", "--pretty=- %s", log_rng, "--"]
    )
    if previous:
        # Normal range: both sides are commits, `..` syntax is correct.
        stat_args = ["diff", "--stat", f"{previous}..{tag}", "--"]
    else:
        # Initial release: _EMPTY_TREE is a tree object, not a commit.
        # Space-separated (not `..`) lets git diff two tree-ish objects directly.
        stat_args = ["diff", "--stat", _EMPTY_TREE, tag, "--"]
    # Stat is non-fatal — suppress its output since we fall back to "" on error.
    stat = await _git(ctx, repo_dir, stat_args, silent=True)
    if stat.startswith("[git error"):
        stat = ""
    date = (await _git(ctx, repo_dir, ["log", "-1", "--format=%cs", tag])).strip()
    return log, stat, date


def _make_git_tool(ctx, repo_dir):
    async def git(args: list[str]) -> str:
        """Run a read-only git command to inspect changes in this repo.

        Pass the subcommand and its arguments as a list. Always include "--"
        before any file path to avoid "ambiguous argument" errors. Examples:
        - ["diff", "--stat", "v1.0.0..v1.1.0", "--"] — see all files changed
        - ["diff", "v1.0.0..v1.1.0", "--", "src/module.py"] — inspect one file
        - ["log", "--oneline", "v1.0.0..v1.1.0", "--"] — compact commit list
        - ["show", "abc1234"] — inspect a single commit

        Allowed subcommands: diff, log, show, shortlog, tag.

        Strategy: call with --stat first to see which files changed, then fetch
        individual files that need clarification. Skip generated or lock files
        (e.g. poetry.lock, package-lock.json, *.pb.go, migration auto-files)
        — their diffs are massive but carry no meaningful changelog signal.
        """
        if not args or args[0] not in _ALLOWED_GIT:
            return (
                "[SYSTEM SUGGESTION] Refused. Only read-only git subcommands are "
                f"allowed: {sorted(_ALLOWED_GIT)}. Put the subcommand first."
            )
        return await _git(ctx, repo_dir, args)

    return git


async def _git(ctx, repo_dir, args, silent=False):
    result, code = await run_command(
        cmd=["git", *args],
        cwd=repo_dir,
        print_method=(lambda *_: None) if silent else ctx.print,
    )
    if code != 0:
        return f"[git error exit={code}]\n{result.error or result.output}".strip()
    return result.output
