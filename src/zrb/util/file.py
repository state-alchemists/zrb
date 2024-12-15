import os


def read_file(file_path: str, replace_map: dict[str, str] = {}) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    for key, val in replace_map.items():
        content = content.replace(key, val)
    return content


def write_file(file_path: str, content: str | list[str]):
    if isinstance(content, list):
        content = "\n".join([line for line in content if line is not None])
    dir_path = os.path.dirname(file_path)
    os.makedirs(dir_path, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content.strip())
