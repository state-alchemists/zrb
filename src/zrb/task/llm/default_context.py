import datetime
import os
import platform
import re
from typing import Any

from zrb.util.file import read_dir, read_file


def get_default_context(user_message: str) -> dict[str, Any]:
    references = re.findall(r"@(\S+)", user_message)
    current_references = []

    for ref in references:
        resource_path = os.path.abspath(os.path.expanduser(ref))
        if os.path.isfile(resource_path):
            content = read_file(resource_path)
            current_references.append(
                {
                    "reference": ref,
                    "name": resource_path,
                    "type": "file",
                    "content": content,
                }
            )
        elif os.path.isdir(resource_path):
            content = read_dir(resource_path)
            current_references.append(
                {
                    "reference": ref,
                    "name": resource_path,
                    "type": "directory",
                    "content": content,
                }
            )

    return {
        "current_time": datetime.datetime.now().isoformat(),
        "current_working_directory": os.getcwd(),
        "current_os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "current_references": current_references,
    }
