from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """# PowerShell dynamic completion script for {command_name}
Register-ArgumentCompleter -Native -CommandName '{command_name}' -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    $commandLine = $commandAst.ToString()
    $tokens = [System.Management.Automation.PSParser]::Tokenize($commandLine, [ref]$null)

    $argsBeforeCursor = @()
    foreach ($token in $tokens) {
        if ($token.Start -lt $cursorPosition) {
            if ($token.Type -in @('CommandArgument', 'String', 'Number')) {
                $argsBeforeCursor += $token.Content
            }
        } else {
            break
        }
    }

    if ($argsBeforeCursor.Count -gt 0 -and $argsBeforeCursor[0] -eq '{command_name}') {
        $argsBeforeCursor = $argsBeforeCursor[1..($argsBeforeCursor.Count-1)]
    }

    $cmdArgs = $argsBeforeCursor -join ' '
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
