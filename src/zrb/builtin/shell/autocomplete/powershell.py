from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """# PowerShell dynamic completion script for {command_name}
# This script registers a custom argument completer for the {command_name} command

function Register-{CommandName}Completion {{
    param()

    $scriptBlock = {{
        param($wordToComplete, $commandAst, $cursorPosition)
        
        # Parse command line to extract arguments before cursor
        $commandLine = $commandAst.ToString()
        
        # Tokenize the command line
        $tokens = [System.Management.Automation.PSParser]::Tokenize($commandLine, [ref]$null)
        
        # Find tokens before cursor position
        $argsBeforeCursor = @()
        foreach ($token in $tokens) {{
            if ($token.Start -lt $cursorPosition) {{
                if ($token.Type -in @('CommandArgument', 'String', 'Number')) {{
                    $argsBeforeCursor += $token.Content
                }}
            }} else {{
                break
            }}
        }}
        
        # Remove the '{command_name}' command itself (first argument)
        if ($argsBeforeCursor.Count -gt 0 -and $argsBeforeCursor[0] -eq '{command_name}') {{
            $argsBeforeCursor = $argsBeforeCursor[1..($argsBeforeCursor.Count-1)]
        }}
        
        # Call {command_name} to get subcommands (mimics bash/zsh behavior)
        $cmdArgs = $argsBeforeCursor -join ' '
        $subcmdOutput = {command_name} shell autocomplete subcmd $cmdArgs 2>$null
        
        if ($subcmdOutput) {{
            # Split the output into completion suggestions
            $suggestions = $subcmdOutput -split '\\s+' | Where-Object {{ $_ -like "$wordToComplete*" }}
            
            # Return CompletionResult objects for better display
            $suggestions | ForEach-Object {{
                [System.Management.Automation.CompletionResult]::new(
                    $_,          # completionText
                    $_,          # listItemText
                    'ParameterValue',  # resultType
                    $_           # toolTip
                )
            }}
        }}
    }}
    
    # Register the completer for the {command_name} command
    Register-ArgumentCompleter -Native -CommandName '{command_name}' -ScriptBlock $scriptBlock
    
    Write-Host "{CommandName} PowerShell autocomplete has been registered." -ForegroundColor Green
    Write-Host "To make it permanent, add this function to your PowerShell profile." -ForegroundColor Yellow
}}

# Simple version for PowerShell 5.1 and earlier
function Register-{CommandName}CompletionSimple {{
    param()
    
    $scriptBlock = {{
        param($wordToComplete, $commandAst, $cursorPosition)
        
        # Simple approach: parse command line as string
        $commandLine = $commandAst.ToString()
        
        # Remove '{command_name}' from beginning
        $commandLine = $commandLine.Trim()
        if ($commandLine.StartsWith('{command_name} ')) {{
            $commandLine = $commandLine.Substring({command_len})
        }}
        
        # Get arguments before cursor
        $beforeCursor = $commandLine.Substring(0, [Math]::Min($cursorPosition, $commandLine.Length))
        $args = $beforeCursor -split '\\s+' | Where-Object {{ $_ -ne '' }}
        
        # Call {command_name} to get subcommands
        $cmdArgs = $args -join ' '
        $subcmdOutput = {command_name} shell autocomplete subcmd $cmdArgs 2>$null
        
        if ($subcmdOutput) {{
            $suggestions = $subcmdOutput -split '\\s+' | Where-Object {{ $_ -like "$wordToComplete*" }}
            $suggestions
        }}
    }}
    
    Register-ArgumentCompleter -Native -CommandName '{command_name}' -ScriptBlock $scriptBlock
    Write-Host "{CommandName} PowerShell autocomplete (simple) has been registered." -ForegroundColor Green
}}

# Export the functions
Export-ModuleMember -Function Register-{CommandName}Completion, Register-{CommandName}CompletionSimple

# Instructions for user
Write-Host @"
# {CommandName} PowerShell Autocomplete Setup
# =================================
#
# To enable {CommandName} autocomplete in PowerShell:
#
# 1. Save this script to a file (e.g., {command_name}-completion.ps1)
# 2. Run it in your current session: .\\{command_name}-completion.ps1
# 3. To make it permanent, add this line to your PowerShell profile:
#    . /path/to/{command_name}-completion.ps1
#
# Your PowerShell profile location can be found with: `$PROFILE
#
# Available functions:
# - Register-{CommandName}Completion: Full-featured version with proper token parsing
# - Register-{CommandName}CompletionSimple: Simpler version for PowerShell 5.1
"@
"""


@make_task(
    name="make-powershell-autocomplete",
    description="Create Zrb autocomplete script for PowerShell",
    group=shell_autocomplete_group,
    alias="powershell",
)
def make_powershell_autocomplete(ctx: AnyContext):
    root_group_name = CFG.ROOT_GROUP_NAME
    # Create a capitalized version for function names
    command_name_capitalized = root_group_name.title().replace("-", "").replace("_", "")

    script = _COMPLETION_SCRIPT.replace("{command_name}", root_group_name)
    script = script.replace("{CommandName}", command_name_capitalized)
    script = script.replace("{command_len}", str(len(root_group_name) + 1))

    return script
