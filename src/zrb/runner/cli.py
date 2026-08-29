import sys
from typing import Any

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig, web_auth_config
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup
from zrb.group.group import Group
from zrb.runner.common_util import get_task_str_kwargs
from zrb.session.session import Session
from zrb.session_state_logger.session_state_logger_factory import session_state_logger
from zrb.task.any_task import AnyTask
from zrb.task.make_task import make_task
from zrb.util.cli.style import (
    stylize_highlight,
    stylize_muted,
    stylize_section_header,
    stylize_warning,
)
from zrb.util.string.conversion import double_quote


class Cli(Group):
    """The root command group, and the entry point `zrb` dispatches through.

    Import the ready-made `cli` singleton rather than constructing this — a
    second instance holds a separate task tree that nothing runs.
    """

    def __init__(self):
        """Build the root group.

        Takes no arguments: `name`, `description`, and `banner` are read from
        config on each access rather than fixed at construction, so changing
        `ROOT_GROUP_NAME` is reflected without rebuilding the tree.
        """
        super().__init__(name="_zrb")

    @property
    def name(self):
        return CFG.ROOT_GROUP_NAME

    @property
    def description(self):
        return CFG.ROOT_GROUP_DESCRIPTION

    @property
    def banner(self) -> str:
        return CFG.BANNER

    def run(self, str_args: list[str] | None = None):
        """Parse CLI arguments and run whatever task they address.

        Args:
            str_args: Arguments as typed, without the program name. Defaults to
                an empty list, which prints the root group's help.

        Returns:
            The task's result, or None when the arguments resolve to a group
            rather than a task, in which case its help is printed.
        """
        if str_args is None:
            str_args = []
        str_kwargs, str_args = self._extract_kwargs_from_args(str_args)
        node, node_path, str_args = self.extract_node(str_args)
        if isinstance(node, AnyGroup):
            self._show_group_info(node)
            return
        if "h" in str_kwargs or "help" in str_kwargs:
            self._show_task_info(node)
            return
        task_str_kwargs = get_task_str_kwargs(
            task=node, str_args=str_args, str_kwargs=str_kwargs, cli_mode=True
        )
        session = None
        try:
            result, session = self._run_task(node, str_args, task_str_kwargs)
            if result is not None:
                print(result)
            return result
        finally:
            run_command = self._get_run_command(node, node_path, task_str_kwargs)
            self._print_run_command(run_command)
            # Print conversation name at the very end (for LLM chat tasks)
            self.print_conversation_name(node, session)

    def _print_run_command(self, run_command: str):
        print(
            stylize_muted("To run again:"),
            stylize_highlight(run_command),
            file=sys.stderr,
        )

    def print_conversation_name(self, task: AnyTask, session: Session | None):
        """Print conversation name if available in shared context."""
        try:
            if session is None:
                return
            conversation_name = session.shared_ctx.xcom.get(
                "__conversation_name__", None
            )
            if conversation_name:
                stylized_label = stylize_muted("Session")
                stylized_conversation_name = stylize_highlight(conversation_name)
                print(
                    stylize_muted(f"{stylized_label}: {stylized_conversation_name}"),
                    file=sys.stderr,
                )
        except (KeyError, AttributeError):
            pass  # Not an LLM chat task or no conversation name

    def _get_run_command(
        self,
        task: AnyTask,
        node_path: list[str],
        task_str_kwargs: dict[str, str],
    ) -> str:
        parts = [self.name] + node_path
        secret_input_names = {
            task_input.name for task_input in task.inputs if task_input.is_secret
        }
        parts += [
            self.get_run_command_param(key, val)
            for key, val in task_str_kwargs.items()
            if key not in secret_input_names
        ]
        return " ".join(parts)

    def get_run_command_param(self, key: str, val: str) -> str:
        """Format a single ``--key val`` CLI param, quoting `val` if needed."""
        if '"' in val or "'" in val or " " in val or val == "":
            return f"--{key} {double_quote(val)}"
        return f"--{key} {val}"

    def _run_task(
        self, task: AnyTask, args: list[str], run_kwargs: dict[str, str]
    ) -> tuple[Any, Session]:
        shared_ctx = SharedContext(args=args)
        session = Session(shared_ctx=shared_ctx, root_group=self)
        result = task.run(session, str_kwargs=run_kwargs)
        return result, session

    def _show_task_info(self, task: AnyTask):
        description = task.description
        inputs = task.inputs
        if description != task.name and description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(description)
            print()
        if len(inputs) > 0:
            print(stylize_section_header("INPUTS"))
            max_input_name_length = max(len(task_input.name) for task_input in inputs)
            for task_input in inputs:
                task_input_name = task_input.name.ljust(max_input_name_length + 1)
                print(f"  --{task_input_name}: {task_input.description}")
            print()

    def _show_group_info(self, group: AnyGroup):
        if group.banner != "":
            print(group.banner)
            print()
        if group.description != group.name and group.description != "":
            print(stylize_section_header("DESCRIPTION"))
            print(group.description)
            print()
        subgroups = group.get_non_empty_subgroups()
        if len(subgroups) > 0:
            print(stylize_section_header("GROUPS"))
            max_subgroup_alias_length = max(len(s) for s in subgroups)
            for alias, subgroup in subgroups.items():
                alias = alias.ljust(max_subgroup_alias_length + 1)
                print(f"  {alias}: {subgroup.description}")
            print()
        subtasks = group.get_subtasks()
        if len(subtasks) > 0:
            print(stylize_section_header("TASKS"))
            max_subtask_alias_length = max(len(s) for s in subtasks)
            for alias, subtask in subtasks.items():
                alias = alias.ljust(max_subtask_alias_length + 1)
                print(f"  {alias}: {subtask.description}")
            print()

    def _extract_kwargs_from_args(
        self, args: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        residual_args = []  # To store positional arguments
        kwargs = {}  # To store options as a dictionary
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("--"):
                # Handle key-value pairs like --keyword=value
                if "=" in arg:
                    key, value = arg[2:].split("=", 1)
                    kwargs[key] = value
                else:
                    # Handle flags like --this followed by a value or set to True
                    key = arg[2:]
                    # Check if the next item is a value or another flag
                    if i + 1 < len(args) and not args[i + 1].startswith("-"):
                        kwargs[key] = args[i + 1]
                        i += 1  # Skip the next argument as it's a value
                    else:
                        kwargs[key] = "true"
            elif arg.startswith("-"):
                # Handle short flags like -t or -n
                key = arg[1:]
                kwargs[key] = "true"
            else:
                # Anything else is considered a positional argument
                residual_args.append(arg)
            i += 1
        return kwargs, residual_args


cli = Cli()


@make_task(name="version", description="🌟 Get current version", retries=0, group=cli)
def get_version(_: AnyContext):
    return CFG.VERSION


server_group = cli.add_group(
    Group(name="server", description="🌐 Server related command")
)


@make_task(
    name="start-server",
    description=f"🚀 Start {CFG.ROOT_GROUP_NAME.capitalize()} Web Server",
    cli_only=True,
    retries=0,
    group=server_group,
    alias="start",
)
async def start_server(_: AnyContext):
    # lazy: heavy third-party
    from uvicorn import Config, Server

    # lazy: zrb internal (heavy via transitive) — pulls in fastapi + the full
    # web route tree; keep it off the CLI-only import path.
    from zrb.runner.web_app import configure_uvicorn_logging, create_web_app

    configure_uvicorn_logging()
    _warn_if_insecure_bind(CFG.WEB_HTTP_HOST, web_auth_config)
    app = create_web_app(cli, web_auth_config, session_state_logger)
    server = Server(
        Config(
            app=app,
            host=CFG.WEB_HTTP_HOST,
            port=CFG.WEB_HTTP_PORT,
            loop="asyncio",
            timeout_graceful_shutdown=CFG.WEB_SHUTDOWN_TIMEOUT // 1000,
        )
    )
    await server.serve()


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _warn_if_insecure_bind(host: str, auth_config: WebAuthConfig) -> None:
    """Warn (never refuse) when a network-exposed bind is not actually safe.

    A non-loopback bind is a legitimate, intentional choice for LAN/container
    deployments, so this never blocks startup — it only makes the risk
    impossible to miss. Inspect the effective auth object because callers may
    override the CFG-backed defaults programmatically.
    """
    if host in _LOOPBACK_HOSTS:
        return
    if not auth_config.enable_auth:
        print(
            stylize_warning(
                f"\nWarning: binding to '{host}' without authentication "
                "(WEB_AUTH_ENABLED=off) exposes task execution to anyone who "
                "can reach this host. Set WEB_AUTH_ENABLED=on, or bind to "
                "127.0.0.1 (the default)."
            ),
            file=sys.stderr,
        )
        return
    stale_defaults = []
    if auth_config.super_admin_password == CFG.DEFAULT_WEB_SUPER_ADMIN_PASSWORD:
        stale_defaults.append("WEB_SUPER_ADMIN_PASSWORD")
    if auth_config.secret_key == CFG.DEFAULT_WEB_SECRET_KEY:
        stale_defaults.append("WEB_SECRET_KEY")
    if stale_defaults:
        print(
            stylize_warning(
                f"\nWarning: binding to '{host}' with authentication enabled, "
                f"but {' and '.join(stale_defaults)} still has its default, "
                "publicly-documented value. Anyone who read zrb's docs has "
                "these credentials. Set them to unique values before "
                "exposing this server."
            ),
            file=sys.stderr,
        )
