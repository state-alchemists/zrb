import os


def approve_if_path_inside_cwd(args: dict[str, any]) -> bool:
    path = args.get("path")
    paths = args.get("paths")
    if path is not None:
        return _is_path_inside_cwd(str(path))
    if paths is not None:
        if isinstance(paths, list):
            return all(_is_path_inside_cwd(str(p)) for p in paths)
        return False
    return True


def _is_path_inside_cwd(path: str) -> bool:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        cwd = os.getcwd()
        return abs_path == cwd or abs_path.startswith(cwd + os.sep)
    except Exception:
        return False
