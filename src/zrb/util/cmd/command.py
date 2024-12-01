import re


def check_unrecommended_commands(cmd_script: str) -> dict[str, str]:
    banned_commands = {
        "<(": "Process substitution isn't POSIX compliant and causes trouble",
        "column": "Command isn't included in Ubuntu packages and is not POSIX compliant",
        "echo": "echo isn't consistent across OS; use printf instead",
        "eval": "Avoid eval as it can accidentally execute arbitrary strings",
        "realpath": "Not available by default on OSX",
        "source": "Not POSIX compliant; use '.' instead",
        " test": "Use '[' instead for consistency",
        "which": "Command in not POSIX compliant, use command -v",
    }
    banned_commands_regex = {
        r"grep.* -y": "grep -y does not work on Alpine; use grep -i",
        r"grep.* -P": "grep -P is not valid on OSX",
        r"grep[^|]+--\w{2,}": "grep long commands do not work on Alpine",
        r'readlink.+-.*f.+["$]': "readlink -f behaves differently on OSX",
        r"sort.*-V": "sort -V is not supported everywhere",
        r"sort.*--sort-versions": "sort --sort-version is not supported everywhere",
        r"\bls ": "Avoid using ls; use shell globs or find instead",
    }
    violations = {}
    # Check banned commands
    for cmd, reason in banned_commands.items():
        if cmd in cmd_script:
            violations[cmd] = reason
    # Check banned regex patterns
    for pattern, reason in banned_commands_regex.items():
        if re.search(pattern, cmd_script):
            violations[pattern] = reason
    return violations
