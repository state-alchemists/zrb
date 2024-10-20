from ....runner.cli import cli
from ....session.session import Session
from ....task.any_task import AnyTask
from ....task.make_task import make_task
from ....util.cli.autocomplete.bash import generate_bash_autocompletion
from ....util.cli.autocomplete.data import get_command_completions
from ._group import shell_autocomplete_group


@make_task(
    name="make-bash-autocomplete",
    description="Create Zrb autocomplete script for bash",
)
def make_bash_autocomplete(t: AnyTask, s: Session):
    command_completions = get_command_completions(cli)
    script = generate_bash_autocompletion(
        cmd=cli.get_name(),
        command_completions=command_completions
    )
    return script


shell_autocomplete_group.add_task(make_bash_autocomplete, "bash")
