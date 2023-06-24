from typing import List
import subprocess


def get_modified_files(commit: str) -> List[str]:
    exit_status, output = subprocess.getstatusoutput(f'git show {commit}')
    if exit_status != 0:
        raise Exception(output)
    lines = output.split('\n')
    files = []
    for line in lines:
        if not line.startswith('---') and not line.startswith('+++'):
            continue
        if line[4:6] != 'a/' and line[4:6] != 'b/':
            continue
        # line should contains something like `--- a/some-file.txt`
        file = line[6:]
        if file not in files:
            files.append(file)
    return files