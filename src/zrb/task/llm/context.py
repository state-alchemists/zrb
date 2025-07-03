import datetime
import os
import platform
import re
from typing import Any

from zrb.util.file import read_dir, read_file_with_line_numbers


def extract_default_context(user_message: str) -> tuple[str, dict[str, Any]]:
    """
    Return modified user message and default context including time, OS, and file references.
    """
    modified_user_message = user_message
    # Match “@” + any non-space/comma sequence that contains at least one “/”
    pattern = r"(?<!\w)@(?=[^,\s]*/)([^,\s]+)"
    potential_resource_path = re.findall(pattern, user_message)
    current_references = []

    for ref in potential_resource_path:
        resource_path = os.path.abspath(os.path.expanduser(ref))
        print("RESOURCE PATH", resource_path)
        if os.path.isfile(resource_path):
            content = read_file_with_line_numbers(resource_path)
            current_references.append(
                {
                    "reference": ref,
                    "name": resource_path,
                    "type": "file",
                    "note": "line numbers are included in the content",
                    "content": content,
                }
            )
            # Remove the '@' from the modified user message for valid file paths
            modified_user_message = modified_user_message.replace(f"@{ref}", ref, 1)
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
            # Remove the '@' from the modified user message for valid directory paths
            modified_user_message = modified_user_message.replace(f"@{ref}", ref, 1)

    context = {
        "current_time": datetime.datetime.now().isoformat(),
        "current_working_directory": os.getcwd(),
        "current_os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "current_references": current_references,
    }

    return modified_user_message, context
