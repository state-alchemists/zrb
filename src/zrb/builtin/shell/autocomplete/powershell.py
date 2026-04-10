from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """# PowerShell dynamic completion script for {command_name}
Register-ArgumentCompleter -Native -CommandName '{command_name}' -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    [Console]::InputEncoding = [Console]::OutputEncoding = $OutputEncoding = [System.Text.Utf8Encoding]::new()

    # CommandElements does NOT include the partial word being typed (that's $wordToComplete).
    # Skip the first element (the command name) and pass the rest as the subcommand path.
    $elements = $commandAst.CommandElements | Select-Object -Skip 1 | ForEach-Object { $_.ToString() }

    $subcmdOutput = {command_name} shell autocomplete subcmd @elements 2>$null

    if ($subcmdOutput) {
        $subcmdOutput -split '\\s+' | Where-Object { $_ -ne '' -and $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    }
}
"""


@make_task(
    name="make-powershell-autocomplete",
    description="Create Zrb autocomplete script for PowerShell",
    group=shell_autocomplete_group,
    alias="powershell",
)
def make_powershell_autocomplete(ctx: AnyContext):
    return _COMPLETION_SCRIPT.replace("{command_name}", CFG.ROOT_GROUP_NAME)
