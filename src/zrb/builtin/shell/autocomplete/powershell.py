from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """# PowerShell dynamic completion script for {command_name}
Register-ArgumentCompleter -Native -CommandName '{command_name}' -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    # Get all typed words from the AST, excluding the command name itself
    $elements = @($commandAst.CommandElements | ForEach-Object { $_.ToString() })
    $subArgs = if ($elements.Count -gt 1) { $elements[1..($elements.Count - 1)] } else { @() }

    # Remove the word currently being completed so subcmd gets the parent path
    if ($wordToComplete -ne '' -and $subArgs.Count -gt 0 -and $subArgs[-1] -eq $wordToComplete) {
        $subArgs = if ($subArgs.Count -gt 1) { $subArgs[0..($subArgs.Count - 2)] } else { @() }
    }

    $cmdArgs = $subArgs -join ' '
    $subcmdOutput = {command_name} shell autocomplete subcmd $cmdArgs 2>$null

    if ($subcmdOutput) {
        $subcmdOutput -split '\\s+' | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
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
