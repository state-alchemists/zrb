from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """# PowerShell dynamic completion script for {command_name}
Register-ArgumentCompleter -Native -CommandName '{command_name}' -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    # CommandElements includes the partial word as the last element when one is being typed.
    # Strip it so subcmd receives only the completed path (mirrors bash COMP_WORDS[0:COMP_CWORD]).
    $elements = @($commandAst.CommandElements | ForEach-Object { $_.ToString() })
    if ($wordToComplete -ne '' -and $elements.Count -gt 0 -and $elements[-1] -eq $wordToComplete) {
        $elements = $elements[0..($elements.Count - 2)]
    }

    # Cache the subcommand list for a minute, keyed by cwd + the command
    # being completed, so repeated Tab presses don't pay a fresh process
    # spawn (and zrb_init.py reload) on every keystroke.
    $cacheKey = (($PWD.Path + ' ' + ($elements -join ' ')) -replace '[^a-zA-Z0-9]', '_')
    $cacheFile = Join-Path $env:TEMP "{command_name}-autocomplete-cache-$cacheKey"

    if ((Test-Path $cacheFile) -and ((Get-Item $cacheFile).LastWriteTime -gt (Get-Date).AddMinutes(-1))) {
        $subcmdOutput = Get-Content $cacheFile -Raw
    } else {
        $subcmdOutput = {command_name} shell autocomplete subcmd $elements 2>$null
        $subcmdOutput | Out-File -FilePath $cacheFile -NoNewline
    }

    if ($subcmdOutput) {
        $subcmdOutput -split '\\s+' | Where-Object { $_ -ne '' -and $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    }
}
"""


@make_task(
    name="make-powershell-autocomplete",
    description="🔷 Create Zrb autocomplete script for PowerShell",
    group=shell_autocomplete_group,
    alias="powershell",
)
def make_powershell_autocomplete(ctx: AnyContext):
    return _COMPLETION_SCRIPT.replace("{command_name}", CFG.ROOT_GROUP_NAME)
